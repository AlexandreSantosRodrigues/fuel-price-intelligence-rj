"""Leakage-safe feature engineering for weekly fuel-price forecasts."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

REQUIRED_WEEKLY_COLUMNS = {
    "week_start",
    "product",
    "observations",
    "stations",
    "median_price",
}


def validate_weekly_input(weekly: pd.DataFrame) -> None:
    """Validate the weekly analytical schema."""
    missing = REQUIRED_WEEKLY_COLUMNS.difference(
        weekly.columns
    )

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(
            "Missing required weekly columns: "
            f"{missing_list}"
        )

    if weekly.empty:
        raise ValueError(
            "The weekly dataset cannot be empty"
        )


def validate_positive_integers(
    values: Iterable[int],
    *,
    parameter_name: str,
) -> tuple[int, ...]:
    """Validate and normalize positive integer parameters."""
    normalized = tuple(values)

    if not normalized:
        raise ValueError(
            f"{parameter_name} cannot be empty"
        )

    if any(
        not isinstance(value, int) or value < 1
        for value in normalized
    ):
        raise ValueError(
            f"{parameter_name} must contain "
            "positive integers"
        )

    return tuple(sorted(set(normalized)))


def regularize_weekly_series(
    weekly: pd.DataFrame,
    *,
    min_coverage_ratio: float = 0.50,
) -> pd.DataFrame:
    """Create complete weekly calendars using causal filling."""
    validate_weekly_input(weekly)

    if not 0 < min_coverage_ratio <= 1:
        raise ValueError(
            "min_coverage_ratio must be between 0 and 1"
        )

    prepared = weekly.copy()
    prepared["week_start"] = pd.to_datetime(
        prepared["week_start"],
        errors="coerce",
    )

    if prepared["week_start"].isna().any():
        raise ValueError(
            "week_start contains invalid values"
        )

    if prepared.duplicated(
        subset=["product", "week_start"]
    ).any():
        raise ValueError(
            "Weekly data contains duplicate "
            "product-week records"
        )

    regularized_groups: list[pd.DataFrame] = []

    for product, group in prepared.groupby(
        "product",
        observed=True,
        sort=True,
    ):
        ordered = (
            group.sort_values("week_start")
            .set_index("week_start")
        )

        calendar = pd.date_range(
            start=ordered.index.min(),
            end=ordered.index.max(),
            freq="7D",
            name="week_start",
        )

        complete = ordered.reindex(calendar)
        complete["product"] = str(product)

        complete["observations"] = pd.to_numeric(
            complete["observations"],
            errors="coerce",
        )
        complete["stations"] = pd.to_numeric(
            complete["stations"],
            errors="coerce",
        )
        complete["median_price"] = pd.to_numeric(
            complete["median_price"],
            errors="coerce",
        )

        typical_observations = float(
            group["observations"].median()
        )

        complete["is_observed"] = (
            complete["median_price"].notna()
        )
        complete["coverage_ratio"] = (
            complete["observations"]
            / typical_observations
        ).fillna(0.0)

        complete["is_reliable_target"] = (
            complete["is_observed"]
            & complete["coverage_ratio"].ge(
                min_coverage_ratio
            )
        )

        reliable_price = complete[
            "median_price"
        ].where(
            complete["is_reliable_target"]
        )

        complete["historical_price"] = (
            reliable_price.ffill()
        )

        complete["observations"] = (
            complete["observations"]
            .fillna(0)
            .astype(int)
        )
        complete["stations"] = (
            complete["stations"]
            .fillna(0)
            .astype(int)
        )

        complete = complete.reset_index()
        regularized_groups.append(complete)

    return (
        pd.concat(
            regularized_groups,
            ignore_index=True,
        )
        .sort_values(
            ["product", "week_start"]
        )
        .reset_index(drop=True)
    )


def build_forecast_features(
    weekly: pd.DataFrame,
    *,
    lags: Iterable[int] = (1, 2, 4, 8, 12),
    rolling_windows: Iterable[int] = (4, 8, 12),
    min_coverage_ratio: float = 0.50,
) -> pd.DataFrame:
    """Build one-week-ahead features using past information only."""
    normalized_lags = validate_positive_integers(
        lags,
        parameter_name="lags",
    )
    normalized_windows = validate_positive_integers(
        rolling_windows,
        parameter_name="rolling_windows",
    )

    regularized = regularize_weekly_series(
        weekly,
        min_coverage_ratio=min_coverage_ratio,
    )

    featured_groups: list[pd.DataFrame] = []
    feature_columns: list[str] = []

    for product, group in regularized.groupby(
        "product",
        observed=True,
        sort=True,
    ):
        featured = (
            group.sort_values("week_start")
            .reset_index(drop=True)
            .copy()
        )

        historical_price = featured[
            "historical_price"
        ]

        current_feature_columns: list[str] = []

        for lag in normalized_lags:
            column = f"lag_{lag}"
            featured[column] = (
                historical_price.shift(lag)
            )
            current_feature_columns.append(column)

        past_only_price = historical_price.shift(1)

        for window in normalized_windows:
            mean_column = (
                f"rolling_mean_{window}"
            )
            std_column = (
                f"rolling_std_{window}"
            )

            featured[mean_column] = (
                past_only_price.rolling(
                    window=window,
                    min_periods=window,
                ).mean()
            )
            featured[std_column] = (
                past_only_price.rolling(
                    window=window,
                    min_periods=window,
                ).std()
            )

            current_feature_columns.extend(
                [mean_column, std_column]
            )

        if {1, 2}.issubset(normalized_lags):
            featured["price_change_1"] = (
                featured["lag_1"]
                - featured["lag_2"]
            )
            current_feature_columns.append(
                "price_change_1"
            )

        if {1, 4}.issubset(normalized_lags):
            featured["price_change_4"] = (
                featured["lag_1"]
                - featured["lag_4"]
            )
            current_feature_columns.append(
                "price_change_4"
            )

        featured["observation_count_lag_1"] = (
            featured["observations"].shift(1)
        )
        featured["station_count_lag_1"] = (
            featured["stations"].shift(1)
        )

        current_feature_columns.extend(
            [
                "observation_count_lag_1",
                "station_count_lag_1",
            ]
        )

        iso_calendar = (
            featured["week_start"]
            .dt.isocalendar()
        )
        featured["year"] = (
            featured["week_start"].dt.year
        )
        featured["month"] = (
            featured["week_start"].dt.month
        )
        featured["week_of_year"] = (
            iso_calendar.week.astype(int)
        )
        featured["week_sin"] = np.sin(
            2
            * np.pi
            * featured["week_of_year"]
            / 52.0
        )
        featured["week_cos"] = np.cos(
            2
            * np.pi
            * featured["week_of_year"]
            / 52.0
        )
        featured["trend"] = np.arange(
            len(featured),
            dtype=int,
        )

        current_feature_columns.extend(
            [
                "year",
                "month",
                "week_of_year",
                "week_sin",
                "week_cos",
                "trend",
            ]
        )

        featured["target_price"] = featured[
            "median_price"
        ]

        valid_mask = (
            featured["is_reliable_target"]
            & featured[
                current_feature_columns
            ].notna().all(axis=1)
        )

        featured_groups.append(
            featured.loc[valid_mask].copy()
        )
        feature_columns = current_feature_columns

    metadata_columns = [
        "week_start",
        "product",
        "target_price",
        "observations",
        "stations",
        "coverage_ratio",
    ]

    result = pd.concat(
        featured_groups,
        ignore_index=True,
    )

    return (
        result[
            metadata_columns + feature_columns
        ]
        .sort_values(
            ["week_start", "product"]
        )
        .reset_index(drop=True)
    )