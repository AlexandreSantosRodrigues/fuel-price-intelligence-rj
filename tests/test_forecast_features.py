"""Tests for leakage-safe forecasting features."""

from __future__ import annotations

import pandas as pd
import pytest

from src.features.forecast import (
    build_forecast_features,
    regularize_weekly_series,
)


def test_regularize_weekly_series_handles_gaps_causally() -> None:
    """Missing and low-coverage weeks must not become targets."""
    weekly = pd.DataFrame(
        {
            "week_start": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-08",
                    "2024-01-22",
                    "2024-01-29",
                ]
            ),
            "product": ["GASOLINA"] * 4,
            "observations": [100, 100, 100, 2],
            "stations": [50, 50, 50, 1],
            "median_price": [5.00, 5.10, 5.30, 9.00],
        }
    )

    regularized = regularize_weekly_series(
        weekly,
        min_coverage_ratio=0.50,
    )

    assert len(regularized) == 5

    missing_week = regularized.loc[
        regularized["week_start"].eq(
            pd.Timestamp("2024-01-15")
        )
    ].iloc[0]

    assert bool(missing_week["is_observed"]) is False
    assert bool(
        missing_week["is_reliable_target"]
    ) is False
    assert missing_week["historical_price"] == pytest.approx(
        5.10
    )

    low_coverage_week = regularized.loc[
        regularized["week_start"].eq(
            pd.Timestamp("2024-01-29")
        )
    ].iloc[0]

    assert bool(low_coverage_week["is_observed"]) is True
    assert bool(
        low_coverage_week["is_reliable_target"]
    ) is False
    assert low_coverage_week[
        "historical_price"
    ] == pytest.approx(5.30)


def test_build_forecast_features_uses_only_past_values() -> None:
    """Features for one week must not depend on its target price."""
    dates = pd.date_range(
        "2024-01-01",
        periods=6,
        freq="7D",
    )
    weekly = pd.DataFrame(
        {
            "week_start": dates,
            "product": ["ETANOL"] * 6,
            "observations": [100] * 6,
            "stations": [50] * 6,
            "median_price": [
                5.00,
                5.10,
                5.20,
                5.30,
                5.40,
                5.50,
            ],
        }
    )

    features = build_forecast_features(
        weekly,
        lags=(1, 2),
        rolling_windows=(2,),
    )

    target_week = pd.Timestamp("2024-01-15")
    row = features.loc[
        features["week_start"].eq(target_week)
    ].iloc[0]

    assert row["target_price"] == pytest.approx(5.20)
    assert row["lag_1"] == pytest.approx(5.10)
    assert row["lag_2"] == pytest.approx(5.00)
    assert row["rolling_mean_2"] == pytest.approx(
        5.05
    )

    changed = weekly.copy()
    changed.loc[
        changed["week_start"].eq(target_week),
        "median_price",
    ] = 99.00

    changed_features = build_forecast_features(
        changed,
        lags=(1, 2),
        rolling_windows=(2,),
    )
    changed_row = changed_features.loc[
        changed_features["week_start"].eq(
            target_week
        )
    ].iloc[0]

    assert changed_row["target_price"] == pytest.approx(
        99.00
    )
    assert changed_row["lag_1"] == pytest.approx(
        row["lag_1"]
    )
    assert changed_row["lag_2"] == pytest.approx(
        row["lag_2"]
    )
    assert changed_row[
        "rolling_mean_2"
    ] == pytest.approx(
        row["rolling_mean_2"]
    )


def test_unreliable_targets_are_excluded() -> None:
    """Low-coverage observations cannot enter model evaluation."""
    weekly = pd.DataFrame(
        {
            "week_start": pd.date_range(
                "2024-01-01",
                periods=5,
                freq="7D",
            ),
            "product": ["GASOLINA"] * 5,
            "observations": [100, 100, 2, 100, 100],
            "stations": [50, 50, 1, 50, 50],
            "median_price": [
                5.00,
                5.10,
                8.50,
                5.20,
                5.30,
            ],
        }
    )

    features = build_forecast_features(
        weekly,
        lags=(1,),
        rolling_windows=(2,),
    )

    assert pd.Timestamp(
        "2024-01-15"
    ) not in set(features["week_start"])