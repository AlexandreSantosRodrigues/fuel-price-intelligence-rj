"""Reusable exploratory analysis for RJ fuel-price data."""

from __future__ import annotations

import pandas as pd

REQUIRED_ANALYTICAL_COLUMNS = {
    "municipality",
    "station_cnpj",
    "product",
    "collection_date",
    "sale_price",
}

COMPETITIVENESS_COLUMNS = [
    "municipality",
    "week_start",
    "gasoline_median",
    "ethanol_median",
    "ethanol_gasoline_ratio",
    "ethanol_competitive",
]


def validate_analysis_input(data: pd.DataFrame) -> None:
    """Validate the minimum schema required by the EDA."""
    missing = REQUIRED_ANALYTICAL_COLUMNS.difference(
        data.columns
    )

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(
            "Missing required analytical columns: "
            f"{missing_list}"
        )

    if data.empty:
        raise ValueError(
            "The analytical dataset cannot be empty"
        )


def add_week_start(data: pd.DataFrame) -> pd.DataFrame:
    """Add the Monday corresponding to each collection week."""
    enriched = data.copy()

    collection_date = pd.to_datetime(
        enriched["collection_date"],
        errors="coerce",
    )

    if collection_date.isna().any():
        raise ValueError(
            "collection_date contains invalid values"
        )

    enriched["week_start"] = (
        collection_date
        - pd.to_timedelta(
            collection_date.dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    return enriched


def build_weekly_price_summary(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate weekly price statistics by product."""
    validate_analysis_input(data)
    enriched = add_week_start(data)

    summary = (
        enriched.groupby(
            ["week_start", "product"],
            as_index=False,
            observed=True,
        )
        .agg(
            observations=("sale_price", "size"),
            stations=("station_cnpj", "nunique"),
            mean_price=("sale_price", "mean"),
            median_price=("sale_price", "median"),
            min_price=("sale_price", "min"),
            max_price=("sale_price", "max"),
            std_price=("sale_price", "std"),
            q1_price=(
                "sale_price",
                lambda values: values.quantile(0.25),
            ),
            q3_price=(
                "sale_price",
                lambda values: values.quantile(0.75),
            ),
        )
        .sort_values(
            ["week_start", "product"]
        )
        .reset_index(drop=True)
    )

    summary["price_range"] = (
        summary["max_price"] - summary["min_price"]
    )
    summary["iqr_price"] = (
        summary["q3_price"] - summary["q1_price"]
    )

    return summary


def build_municipality_summary(
    data: pd.DataFrame,
    *,
    min_observations: int = 30,
) -> pd.DataFrame:
    """Aggregate municipality statistics with sample control."""
    if min_observations < 1:
        raise ValueError(
            "min_observations must be at least 1"
        )

    validate_analysis_input(data)

    summary = (
        data.groupby(
            ["municipality", "product"],
            as_index=False,
            observed=True,
        )
        .agg(
            observations=("sale_price", "size"),
            stations=("station_cnpj", "nunique"),
            mean_price=("sale_price", "mean"),
            median_price=("sale_price", "median"),
            min_price=("sale_price", "min"),
            max_price=("sale_price", "max"),
            std_price=("sale_price", "std"),
            q1_price=(
                "sale_price",
                lambda values: values.quantile(0.25),
            ),
            q3_price=(
                "sale_price",
                lambda values: values.quantile(0.75),
            ),
        )
    )

    summary["price_range"] = (
        summary["max_price"] - summary["min_price"]
    )
    summary["iqr_price"] = (
        summary["q3_price"] - summary["q1_price"]
    )

    return (
        summary.loc[
            summary["observations"] >= min_observations
        ]
        .sort_values(
            ["product", "median_price", "municipality"]
        )
        .reset_index(drop=True)
    )

def build_municipality_price_index(
    data: pd.DataFrame,
    *,
    min_observations: int = 100,
    min_weeks: int = 8,
) -> pd.DataFrame:
    """Compare municipalities against the same weekly market context."""
    if min_observations < 1:
        raise ValueError(
            "min_observations must be at least 1"
        )

    if min_weeks < 1:
        raise ValueError(
            "min_weeks must be at least 1"
        )

    validate_analysis_input(data)
    enriched = add_week_start(data)

    municipality_week = (
        enriched.groupby(
            [
                "municipality",
                "week_start",
                "product",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            municipality_week_median=(
                "sale_price",
                "median",
            ),
            observations=("sale_price", "size"),
        )
    )

    state_week = (
        municipality_week.groupby(
            ["week_start", "product"],
            as_index=False,
            observed=True,
        )
        .agg(
            state_week_median=(
                "municipality_week_median",
                "median",
            )
        )
    )

    comparison = municipality_week.merge(
        state_week,
        on=["week_start", "product"],
        how="left",
        validate="many_to_one",
    )

    comparison["relative_price"] = (
        comparison["municipality_week_median"]
        / comparison["state_week_median"]
        - 1
    )

    station_counts = (
        enriched.groupby(
            ["municipality", "product"],
            as_index=False,
            observed=True,
        )
        .agg(stations=("station_cnpj", "nunique"))
    )

    summary = (
        comparison.groupby(
            ["municipality", "product"],
            as_index=False,
            observed=True,
        )
        .agg(
            observations=("observations", "sum"),
            weeks=("week_start", "nunique"),
            median_price=(
                "municipality_week_median",
                "median",
            ),
            median_relative_price=(
                "relative_price",
                "median",
            ),
            mean_relative_price=(
                "relative_price",
                "mean",
            ),
        )
        .merge(
            station_counts,
            on=["municipality", "product"],
            how="left",
            validate="one_to_one",
        )
    )

    summary["median_relative_price_pct"] = (
        summary["median_relative_price"] * 100
    )

    return (
        summary.loc[
            (summary["observations"] >= min_observations)
            & (summary["weeks"] >= min_weeks)
        ]
        .sort_values(
            [
                "product",
                "median_relative_price",
                "municipality",
            ]
        )
        .reset_index(drop=True)
    )

def build_ethanol_competitiveness(
    data: pd.DataFrame,
    *,
    competitiveness_threshold: float = 0.70,
) -> pd.DataFrame:
    """Compare weekly ethanol and gasoline medians by municipality."""
    if competitiveness_threshold <= 0:
        raise ValueError(
            "competitiveness_threshold must be positive"
        )

    validate_analysis_input(data)
    enriched = add_week_start(data)

    medians = (
        enriched.groupby(
            ["municipality", "week_start", "product"],
            as_index=False,
            observed=True,
        )
        .agg(median_price=("sale_price", "median"))
    )

    pivoted = medians.pivot(
        index=["municipality", "week_start"],
        columns="product",
        values="median_price",
    ).reset_index()
    pivoted.columns.name = None

    required_products = {"GASOLINA", "ETANOL"}

    if not required_products.issubset(pivoted.columns):
        return pd.DataFrame(
            columns=COMPETITIVENESS_COLUMNS
        )

    comparison = pivoted.dropna(
        subset=["GASOLINA", "ETANOL"]
    ).rename(
        columns={
            "GASOLINA": "gasoline_median",
            "ETANOL": "ethanol_median",
        }
    )

    comparison["ethanol_gasoline_ratio"] = (
        comparison["ethanol_median"]
        / comparison["gasoline_median"]
    )
    comparison["ethanol_competitive"] = (
        comparison["ethanol_gasoline_ratio"]
        <= competitiveness_threshold
    )

    return (
        comparison[COMPETITIVENESS_COLUMNS]
        .sort_values(
            ["week_start", "municipality"]
        )
        .reset_index(drop=True)
    )