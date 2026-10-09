"""Data preparation helpers for the Streamlit application."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

WEEKLY_REQUIRED_COLUMNS = {
    "week_start",
    "product",
    "observations",
    "stations",
    "median_price",
}

COMPETITIVENESS_REQUIRED_COLUMNS = {
    "municipality",
    "week_start",
    "gasoline_median",
    "ethanol_median",
    "ethanol_gasoline_ratio",
    "ethanol_competitive",
}

MUNICIPALITY_REQUIRED_COLUMNS = {
    "municipality",
    "product",
    "observations",
    "weeks",
    "median_price",
    "stations",
    "median_relative_price_pct",
}

METRICS_REQUIRED_COLUMNS = {
    "product",
    "model",
    "predictions",
    "folds",
    "mae",
    "rmse",
    "wape",
    "bias",
    "baseline_mae",
    "mae_improvement_vs_baseline_pct",
}

MODEL_LABELS = {
    "naive_last_price": "Último preço conhecido",
    "ridge": "Regressão Ridge",
    "random_forest": "Random Forest",
    "hist_gradient_boosting": "HistGradientBoosting",
}


def validate_columns(
    data: pd.DataFrame,
    required_columns: set[str],
    dataset_name: str,
) -> None:
    """Raise a clear error when a report has an invalid schema."""
    missing_columns = sorted(
        required_columns - set(data.columns)
    )

    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(
            f"{dataset_name} is missing required columns: "
            f"{missing_text}"
        )


def read_report(
    path: Path,
    *,
    dataset_name: str,
    required_columns: set[str],
    date_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Read and validate one versioned dashboard report."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Dashboard report not found: {path}"
        )

    data = pd.read_csv(path)

    validate_columns(
        data,
        required_columns=required_columns,
        dataset_name=dataset_name,
    )

    for column in date_columns:
        data[column] = pd.to_datetime(
            data[column],
            errors="raise",
        )

    return data


def load_dashboard_data(
    *,
    weekly_path: Path,
    competitiveness_path: Path,
    municipality_path: Path,
    metrics_path: Path,
) -> dict[str, pd.DataFrame]:
    """Load the versioned analytical artifacts used by the app."""
    weekly = read_report(
        weekly_path,
        dataset_name="weekly price summary",
        required_columns=WEEKLY_REQUIRED_COLUMNS,
        date_columns=("week_start",),
    )

    competitiveness = read_report(
        competitiveness_path,
        dataset_name="ethanol competitiveness",
        required_columns=COMPETITIVENESS_REQUIRED_COLUMNS,
        date_columns=("week_start",),
    )

    municipality = read_report(
        municipality_path,
        dataset_name="municipality price index",
        required_columns=MUNICIPALITY_REQUIRED_COLUMNS,
    )

    metrics = read_report(
        metrics_path,
        dataset_name="model metrics",
        required_columns=METRICS_REQUIRED_COLUMNS,
    )

    return {
        "weekly": weekly,
        "competitiveness": competitiveness,
        "municipality": municipality,
        "metrics": metrics,
    }


def build_current_snapshot(
    weekly_data: pd.DataFrame,
) -> pd.DataFrame:
    """Return the latest price and baseline forecast per product."""
    validate_columns(
        weekly_data,
        required_columns=WEEKLY_REQUIRED_COLUMNS,
        dataset_name="weekly price summary",
    )

    if weekly_data.empty:
        raise ValueError(
            "weekly price summary cannot be empty"
        )

    ordered = weekly_data.sort_values(
        ["product", "week_start"]
    )

    latest = (
        ordered.groupby(
            "product",
            observed=True,
            as_index=False,
        )
        .tail(1)
        .copy()
        .sort_values("product")
        .reset_index(drop=True)
    )

    latest["forecast_week"] = (
        latest["week_start"] + pd.Timedelta(weeks=1)
    )

    latest["forecast_next_week"] = latest[
        "median_price"
    ]

    latest["forecast_method"] = (
        "Último preço conhecido"
    )

    return latest


def build_model_comparison(
    metrics: pd.DataFrame,
) -> pd.DataFrame:
    """Rank models by MAE independently for each product."""
    validate_columns(
        metrics,
        required_columns=METRICS_REQUIRED_COLUMNS,
        dataset_name="model metrics",
    )

    if metrics.empty:
        raise ValueError("model metrics cannot be empty")

    comparison = metrics.copy()

    comparison["model_label"] = (
        comparison["model"]
        .map(MODEL_LABELS)
        .fillna(comparison["model"])
    )

    comparison["rank"] = (
        comparison.groupby(
            "product",
            observed=True,
        )["mae"]
        .rank(
            method="dense",
            ascending=True,
        )
        .astype(int)
    )

    comparison["wape_pct"] = (
        comparison["wape"] * 100
    )

    comparison["bias_cents"] = (
        comparison["bias"] * 100
    )

    return comparison.sort_values(
        ["product", "rank", "model"]
    ).reset_index(drop=True)


def build_municipality_ranking(
    municipality_data: pd.DataFrame,
    *,
    product: str,
) -> pd.DataFrame:
    """Return adjusted municipality prices for one product."""
    validate_columns(
        municipality_data,
        required_columns=MUNICIPALITY_REQUIRED_COLUMNS,
        dataset_name="municipality price index",
    )

    normalized_product = product.strip().upper()

    ranking = municipality_data.loc[
        municipality_data["product"].eq(
            normalized_product
        )
    ].copy()

    if ranking.empty:
        available_products = sorted(
            municipality_data["product"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            f"Unknown product: {product}. "
            f"Available products: {available_products}"
        )

    return ranking.sort_values(
        [
            "median_relative_price_pct",
            "municipality",
        ]
    ).reset_index(drop=True)


def build_latest_competitiveness(
    competitiveness_data: pd.DataFrame,
) -> dict[str, object]:
    """Summarize ethanol competitiveness in the latest week."""
    validate_columns(
        competitiveness_data,
        required_columns=COMPETITIVENESS_REQUIRED_COLUMNS,
        dataset_name="ethanol competitiveness",
    )

    if competitiveness_data.empty:
        raise ValueError(
            "ethanol competitiveness cannot be empty"
        )

    latest_week = competitiveness_data[
        "week_start"
    ].max()

    latest = competitiveness_data.loc[
        competitiveness_data["week_start"].eq(
            latest_week
        )
    ].copy()

    comparisons = int(len(latest))
    competitive_count = int(
        latest["ethanol_competitive"].sum()
    )

    competitive_rate = (
        competitive_count / comparisons
        if comparisons
        else 0.0
    )

    return {
        "week_start": latest_week,
        "comparisons": comparisons,
        "competitive_count": competitive_count,
        "competitive_rate": competitive_rate,
        "median_ratio": float(
            latest["ethanol_gasoline_ratio"].median()
        ),
    }


def build_recent_history(
    weekly_data: pd.DataFrame,
    *,
    weeks: int = 26,
) -> pd.DataFrame:
    """Return the most recent number of weeks per product."""
    if weeks < 1:
        raise ValueError("weeks must be at least 1")

    validate_columns(
        weekly_data,
        required_columns=WEEKLY_REQUIRED_COLUMNS,
        dataset_name="weekly price summary",
    )

    return (
        weekly_data.sort_values(
            ["product", "week_start"]
        )
        .groupby(
            "product",
            observed=True,
            group_keys=False,
        )
        .tail(weeks)
        .sort_values(["week_start", "product"])
        .reset_index(drop=True)
    )