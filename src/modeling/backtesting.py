"""Chronological backtesting and forecast evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.base import RegressorMixin, clone
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def expanding_window_splits(
    *,
    n_samples: int,
    initial_train_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Create expanding chronological train-test windows."""
    if n_samples < 1:
        raise ValueError(
            "n_samples must be at least 1"
        )

    if initial_train_size < 1:
        raise ValueError(
            "initial_train_size must be at least 1"
        )

    if test_size < 1:
        raise ValueError(
            "test_size must be at least 1"
        )

    if step_size is None:
        step_size = test_size

    if step_size < 1:
        raise ValueError(
            "step_size must be at least 1"
        )

    if initial_train_size + test_size > n_samples:
        raise ValueError(
            "Not enough samples for the first split"
        )

    splits: list[
        tuple[np.ndarray, np.ndarray]
    ] = []

    for train_end in range(
        initial_train_size,
        n_samples - test_size + 1,
        step_size,
    ):
        train_indices = np.arange(
            0,
            train_end,
            dtype=int,
        )
        test_indices = np.arange(
            train_end,
            train_end + test_size,
            dtype=int,
        )
        splits.append(
            (train_indices, test_indices)
        )

    return splits


def calculate_metrics(
    *,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Calculate forecast-error metrics."""
    actual = np.asarray(
        y_true,
        dtype=float,
    )
    predicted = np.asarray(
        y_pred,
        dtype=float,
    )

    if actual.shape != predicted.shape:
        raise ValueError(
            "y_true and y_pred must have the same shape"
        )

    if actual.size == 0:
        raise ValueError(
            "Metric arrays cannot be empty"
        )

    if not (
        np.isfinite(actual).all()
        and np.isfinite(predicted).all()
    ):
        raise ValueError(
            "Metric arrays must contain finite values"
        )

    errors = predicted - actual
    absolute_errors = np.abs(errors)

    denominator = np.abs(actual).sum()

    if denominator == 0:
        raise ValueError(
            "WAPE is undefined when actual values sum to zero"
        )

    return {
        "mae": float(absolute_errors.mean()),
        "rmse": float(
            np.sqrt(np.mean(np.square(errors)))
        ),
        "wape": float(
            absolute_errors.sum() / denominator
        ),
        "bias": float(errors.mean()),
    }


def default_models() -> dict[str, RegressorMixin]:
    """Return the candidate regression models."""
    return {
        "ridge": Pipeline(
            steps=[
                (
                    "scaler",
                    StandardScaler(),
                ),
                (
                    "model",
                    Ridge(alpha=1.0),
                ),
            ]
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=400,
            max_depth=6,
            min_samples_leaf=3,
            max_features=0.8,
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": (
            HistGradientBoostingRegressor(
                learning_rate=0.05,
                max_iter=200,
                max_leaf_nodes=15,
                min_samples_leaf=10,
                l2_regularization=1.0,
                random_state=42,
            )
        ),
    }


def validate_backtest_input(
    data: pd.DataFrame,
    feature_columns: Sequence[str],
) -> None:
    """Validate modeling columns and numeric values."""
    required = {
        "week_start",
        "product",
        "target_price",
        "lag_1",
        *feature_columns,
    }
    missing = required.difference(data.columns)

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(
            "Missing required modeling columns: "
            f"{missing_list}"
        )

    if data.empty:
        raise ValueError(
            "The modeling dataset cannot be empty"
        )

    if not feature_columns:
        raise ValueError(
            "feature_columns cannot be empty"
        )

    numeric_columns = [
        "target_price",
        "lag_1",
        *feature_columns,
    ]

    numeric = data[
        list(dict.fromkeys(numeric_columns))
    ].apply(
        pd.to_numeric,
        errors="coerce",
    )

    if numeric.isna().any().any():
        raise ValueError(
            "Modeling columns contain missing "
            "or non-numeric values"
        )

    if not np.isfinite(
        numeric.to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "Modeling columns must contain finite values"
        )


def prediction_records(
    *,
    product: str,
    model_name: str,
    fold: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    predictions: np.ndarray,
) -> list[dict[str, object]]:
    """Build detailed prediction records for one fold."""
    records: list[dict[str, object]] = []

    for position, (_, row) in enumerate(
        test.iterrows()
    ):
        actual = float(row["target_price"])
        prediction = float(predictions[position])
        error = prediction - actual

        records.append(
            {
                "product": product,
                "model": model_name,
                "fold": fold,
                "train_start": train[
                    "week_start"
                ].min(),
                "train_end": train[
                    "week_start"
                ].max(),
                "week_start": row["week_start"],
                "actual": actual,
                "prediction": prediction,
                "error": error,
                "absolute_error": abs(error),
                "squared_error": error**2,
            }
        )

    return records


def backtest_models(
    data: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    models: Mapping[
        str,
        RegressorMixin,
    ]
    | None = None,
    initial_train_size: int = 52,
    test_size: int = 4,
    step_size: int = 4,
) -> pd.DataFrame:
    """Backtest candidate models with expanding windows."""
    validate_backtest_input(
        data,
        feature_columns,
    )

    candidate_models = (
        dict(models)
        if models is not None
        else default_models()
    )

    if not candidate_models:
        raise ValueError(
            "At least one candidate model is required"
        )

    prepared = data.copy()
    prepared["week_start"] = pd.to_datetime(
        prepared["week_start"],
        errors="coerce",
    )

    if prepared["week_start"].isna().any():
        raise ValueError(
            "week_start contains invalid values"
        )

    all_records: list[dict[str, object]] = []

    for product, group in prepared.groupby(
        "product",
        observed=True,
        sort=True,
    ):
        ordered = (
            group.sort_values("week_start")
            .reset_index(drop=True)
        )

        splits = expanding_window_splits(
            n_samples=len(ordered),
            initial_train_size=(
                initial_train_size
            ),
            test_size=test_size,
            step_size=step_size,
        )

        for fold, (
            train_indices,
            test_indices,
        ) in enumerate(splits, start=1):
            train = ordered.iloc[
                train_indices
            ].copy()
            test = ordered.iloc[
                test_indices
            ].copy()

            baseline_predictions = (
                test["lag_1"].to_numpy(
                    dtype=float
                )
            )
            all_records.extend(
                prediction_records(
                    product=str(product),
                    model_name=(
                        "naive_last_price"
                    ),
                    fold=fold,
                    train=train,
                    test=test,
                    predictions=(
                        baseline_predictions
                    ),
                )
            )

            x_train = train[
                list(feature_columns)
            ]
            y_train = train[
                "target_price"
            ]
            x_test = test[
                list(feature_columns)
            ]

            for model_name, estimator in (
                candidate_models.items()
            ):
                fitted = clone(estimator)
                fitted.fit(
                    x_train,
                    y_train,
                )
                predictions = np.asarray(
                    fitted.predict(x_test),
                    dtype=float,
                )

                all_records.extend(
                    prediction_records(
                        product=str(product),
                        model_name=model_name,
                        fold=fold,
                        train=train,
                        test=test,
                        predictions=predictions,
                    )
                )

    return (
        pd.DataFrame(all_records)
        .sort_values(
            [
                "product",
                "week_start",
                "model",
            ]
        )
        .reset_index(drop=True)
    )


def summarize_metrics(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize metrics by product and model."""
    required = {
        "product",
        "model",
        "fold",
        "actual",
        "prediction",
    }
    missing = required.difference(
        predictions.columns
    )

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(
            "Missing prediction columns: "
            f"{missing_list}"
        )

    records: list[dict[str, object]] = []

    for (
        product,
        model_name,
    ), group in predictions.groupby(
        ["product", "model"],
        observed=True,
        sort=True,
    ):
        metrics = calculate_metrics(
            y_true=group[
                "actual"
            ].to_numpy(),
            y_pred=group[
                "prediction"
            ].to_numpy(),
        )

        records.append(
            {
                "product": str(product),
                "model": str(model_name),
                "predictions": int(
                    len(group)
                ),
                "folds": int(
                    group["fold"].nunique()
                ),
                **metrics,
            }
        )

    summary = pd.DataFrame(records)

    baseline_mae = (
        summary.loc[
            summary["model"].eq(
                "naive_last_price"
            ),
            ["product", "mae"],
        ]
        .rename(
            columns={
                "mae": "baseline_mae"
            }
        )
    )

    summary = summary.merge(
        baseline_mae,
        on="product",
        how="left",
        validate="many_to_one",
    )

    summary[
        "mae_improvement_vs_baseline_pct"
    ] = (
        1
        - summary["mae"]
        / summary["baseline_mae"]
    ) * 100

    return (
        summary.sort_values(
            ["product", "mae"]
        )
        .reset_index(drop=True)
    )