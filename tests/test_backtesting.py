"""Tests for chronological model evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from src.modeling.backtesting import (
    backtest_models,
    calculate_metrics,
    expanding_window_splits,
    summarize_metrics,
)


def test_expanding_window_splits_preserve_time_order() -> None:
    """Every training window must finish before its test window."""
    splits = expanding_window_splits(
        n_samples=12,
        initial_train_size=6,
        test_size=2,
        step_size=2,
    )

    assert len(splits) == 3

    first_train, first_test = splits[0]
    last_train, last_test = splits[-1]

    assert first_train.tolist() == [0, 1, 2, 3, 4, 5]
    assert first_test.tolist() == [6, 7]
    assert last_train.tolist() == list(range(10))
    assert last_test.tolist() == [10, 11]

    for train_indices, test_indices in splits:
        assert train_indices.max() < test_indices.min()


def test_calculate_metrics() -> None:
    """Forecast metrics must follow their documented definitions."""
    metrics = calculate_metrics(
        y_true=np.array([10.0, 20.0]),
        y_pred=np.array([9.0, 22.0]),
    )

    assert metrics["mae"] == pytest.approx(1.5)
    assert metrics["rmse"] == pytest.approx(
        np.sqrt(2.5)
    )
    assert metrics["wape"] == pytest.approx(0.10)
    assert metrics["bias"] == pytest.approx(0.5)


def test_backtest_models_generates_temporal_predictions() -> None:
    """Backtesting must evaluate models only on future observations."""
    dates = pd.date_range(
        "2024-01-01",
        periods=12,
        freq="7D",
    )
    target = np.linspace(5.0, 6.1, 12)

    data = pd.DataFrame(
        {
            "week_start": dates,
            "product": ["GASOLINA"] * 12,
            "target_price": target,
            "lag_1": np.concatenate(
                ([4.9], target[:-1])
            ),
            "trend": np.arange(12),
        }
    )

    predictions = backtest_models(
        data,
        feature_columns=["lag_1", "trend"],
        models={
            "ridge": Ridge(alpha=1.0),
        },
        initial_train_size=6,
        test_size=2,
        step_size=2,
    )

    assert set(predictions["model"]) == {
        "naive_last_price",
        "ridge",
    }
    assert len(predictions) == 12

    baseline = predictions.loc[
        predictions["model"].eq(
            "naive_last_price"
        )
    ]
    expected_baseline = data.set_index(
        "week_start"
    ).loc[
        baseline["week_start"],
        "lag_1",
    ].to_numpy()

    assert np.allclose(
        baseline["prediction"],
        expected_baseline,
    )
    assert (
        predictions["train_end"]
        < predictions["week_start"]
    ).all()

    summary = summarize_metrics(predictions)

    assert set(summary["model"]) == {
        "naive_last_price",
        "ridge",
    }
    assert {
        "mae",
        "rmse",
        "wape",
        "bias",
    }.issubset(summary.columns)