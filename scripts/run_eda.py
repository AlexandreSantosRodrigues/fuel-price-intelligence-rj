"""Generate reproducible EDA artifacts for RJ fuel prices."""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px

from src.analysis.eda import (
    build_ethanol_competitiveness,
    build_municipality_price_index,
    build_municipality_summary,
    build_weekly_price_summary,
    validate_analysis_input,
)
from src.settings import (
    FIGURES_DIR,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
)

EDA_REPORTS_DIR = REPORTS_DIR / "eda"


def write_figure(
    figure: object,
    destination: Path,
) -> None:
    """Write interactive HTML and static PNG visualizations."""
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.write_html(
        destination,
        include_plotlyjs="cdn",
        full_html=True,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"setDaemon\(\) is deprecated.*",
            category=DeprecationWarning,
        )
        figure.write_image(
            destination.with_suffix(".png"),
            width=1400,
            height=800,
            scale=1.5,
        )



def product_statistics(
    data: pd.DataFrame,
) -> dict[str, dict[str, float | int]]:
    """Create JSON-serializable descriptive statistics."""
    grouped = data.groupby(
        "product",
        observed=True,
    )["sale_price"]

    result: dict[str, dict[str, float | int]] = {}

    for product, prices in grouped:
        result[str(product)] = {
            "observations": int(prices.size),
            "mean": round(float(prices.mean()), 4),
            "median": round(float(prices.median()), 4),
            "standard_deviation": round(
                float(prices.std()),
                4,
            ),
            "minimum": round(
                float(prices.min()),
                4,
            ),
            "maximum": round(
                float(prices.max()),
                4,
            ),
            "q1": round(
                float(prices.quantile(0.25)),
                4,
            ),
            "q3": round(
                float(prices.quantile(0.75)),
                4,
            ),
        }

    return result


def municipality_adjusted_extremes(
    summary: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    """Identify municipalities below and above weekly benchmarks."""
    result: dict[str, dict[str, object]] = {}

    for product, group in summary.groupby(
        "product",
        observed=True,
    ):
        ordered = group.sort_values(
            "median_relative_price"
        )

        lowest = ordered.iloc[0]
        highest = ordered.iloc[-1]

        result[str(product)] = {
            "lowest_relative_municipality": str(
                lowest["municipality"]
            ),
            "lowest_relative_price_pct": round(
                float(
                    lowest[
                        "median_relative_price_pct"
                    ]
                ),
                4,
            ),
            "highest_relative_municipality": str(
                highest["municipality"]
            ),
            "highest_relative_price_pct": round(
                float(
                    highest[
                        "median_relative_price_pct"
                    ]
                ),
                4,
            ),
        }

    return result


def main() -> None:
    """Run the complete exploratory-analysis workflow."""
    input_path = (
        PROCESSED_DATA_DIR
        / "rj_fuel_prices.parquet"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {input_path}"
        )

    data = pd.read_parquet(input_path)
    validate_analysis_input(data)

    EDA_REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    FIGURES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    weekly = build_weekly_price_summary(data)

    municipalities = build_municipality_summary(
        data,
        min_observations=100,
    )

    municipality_index = (
        build_municipality_price_index(
            data,
            min_observations=100,
            min_weeks=8,
        )
    )

    competitiveness = (
        build_ethanol_competitiveness(data)
    )

    weekly_path = (
        EDA_REPORTS_DIR
        / "weekly_price_summary.csv"
    )
    municipality_path = (
        EDA_REPORTS_DIR
        / "municipality_price_summary.csv"
    )
    municipality_index_path = (
        EDA_REPORTS_DIR
        / "municipality_price_index.csv"
    )
    competitiveness_path = (
        EDA_REPORTS_DIR
        / "ethanol_competitiveness.csv"
    )
    summary_path = (
        EDA_REPORTS_DIR
        / "eda_summary.json"
    )

    weekly.to_csv(
        weekly_path,
        index=False,
    )
    municipalities.to_csv(
        municipality_path,
        index=False,
    )
    municipality_index.to_csv(
        municipality_index_path,
        index=False,
    )
    competitiveness.to_csv(
        competitiveness_path,
        index=False,
    )

    competitiveness_rate = 0.0
    median_ratio = None

    if not competitiveness.empty:
        competitiveness_rate = round(
            float(
                competitiveness[
                    "ethanol_competitive"
                ].mean()
            ),
            4,
        )
        median_ratio = round(
            float(
                competitiveness[
                    "ethanol_gasoline_ratio"
                ].median()
            ),
            4,
        )

    summary = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "input_path": (
            "data/processed/"
            "rj_fuel_prices.parquet"
        ),
        "rows": int(len(data)),
        "stations": int(
            data["station_cnpj"].nunique()
        ),
        "municipalities": int(
            data["municipality"].nunique()
        ),
        "date_min": (
            data["collection_date"]
            .min()
            .date()
            .isoformat()
        ),
        "date_max": (
            data["collection_date"]
            .max()
            .date()
            .isoformat()
        ),
        "product_statistics": (
            product_statistics(data)
        ),
        "municipality_adjusted_extremes": (
            municipality_adjusted_extremes(
                municipality_index
            )
        ),
        "ethanol_competitiveness": {
            "threshold": 0.70,
            "municipality_week_comparisons": int(
                len(competitiveness)
            ),
            "competitive_comparisons": int(
                competitiveness[
                    "ethanol_competitive"
                ].sum()
            ),
            "competitive_rate": (
                competitiveness_rate
            ),
            "median_ratio": median_ratio,
        },
    }

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    weekly_figure = px.line(
        weekly,
        x="week_start",
        y="median_price",
        color="product",
        markers=True,
        title=(
            "Mediana semanal dos preços "
            "de combustíveis no RJ"
        ),
        labels={
            "week_start": "Semana",
            "median_price": (
                "Preço mediano (R$/litro)"
            ),
            "product": "Produto",
        },
    )
    weekly_figure.update_layout(
        hovermode="x unified"
    )
    write_figure(
        weekly_figure,
        FIGURES_DIR
        / "weekly_median_prices.html",
    )

    distribution_figure = px.box(
        data,
        x="product",
        y="sale_price",
        color="product",
        points=False,
        title=(
            "Distribuição dos preços "
            "por combustível"
        ),
        labels={
            "product": "Produto",
            "sale_price": "Preço (R$/litro)",
        },
    )
    distribution_figure.update_layout(
        showlegend=False
    )
    write_figure(
        distribution_figure,
        FIGURES_DIR
        / "price_distribution.html",
    )

    municipality_figure = px.bar(
        municipality_index.sort_values(
            [
                "product",
                "median_relative_price_pct",
            ]
        ),
        x="median_relative_price_pct",
        y="municipality",
        color="product",
        facet_col="product",
        orientation="h",
        title=(
            "Preço municipal em relação "
            "à mediana estadual da mesma semana"
        ),
        labels={
            "median_relative_price_pct": (
                "Diferença para a referência "
                "estadual (%)"
            ),
            "municipality": "Município",
            "product": "Produto",
        },
    )
    municipality_figure.add_vline(
        x=0,
        line_dash="dash",
    )
    municipality_figure.for_each_annotation(
        lambda annotation: annotation.update(
            text=annotation.text.split("=")[-1]
        )
    )
    write_figure(
        municipality_figure,
        FIGURES_DIR
        / "municipality_adjusted_price_index.html",
    )

    weekly_competitiveness = (
        competitiveness.groupby(
            "week_start",
            as_index=False,
            observed=True,
        )
        .agg(
            median_ratio=(
                "ethanol_gasoline_ratio",
                "median",
            ),
            competitive_rate=(
                "ethanol_competitive",
                "mean",
            ),
        )
    )

    competitiveness_figure = px.line(
        weekly_competitiveness,
        x="week_start",
        y="median_ratio",
        title=(
            "Relação semanal entre os preços "
            "de etanol e gasolina"
        ),
        labels={
            "week_start": "Semana",
            "median_ratio": (
                "Preço do etanol / gasolina"
            ),
        },
    )
    competitiveness_figure.add_hline(
        y=0.70,
        line_dash="dash",
        annotation_text=(
            "Referência de competitividade: 70%"
        ),
    )
    write_figure(
        competitiveness_figure,
        FIGURES_DIR
        / "ethanol_competitiveness.html",
    )

    print("Exploratory analysis completed.")
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()