"""Compare weekly fuel-price forecasting models."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.modeling.backtesting import (
    backtest_models,
    summarize_metrics,
)
from src.settings import (
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
)

MODELING_REPORTS_DIR = REPORTS_DIR / "modeling"

METADATA_COLUMNS = {
    "week_start",
    "product",
    "target_price",
    "observations",
    "stations",
    "coverage_ratio",
}


def serialize_metrics(
    metrics: pd.DataFrame,
) -> list[dict[str, object]]:
    """Convert model metrics into JSON-safe records."""
    records: list[dict[str, object]] = []

    for row in metrics.to_dict(
        orient="records"
    ):
        records.append(
            {
                "product": str(row["product"]),
                "model": str(row["model"]),
                "predictions": int(
                    row["predictions"]
                ),
                "folds": int(row["folds"]),
                "mae": round(
                    float(row["mae"]),
                    6,
                ),
                "rmse": round(
                    float(row["rmse"]),
                    6,
                ),
                "wape": round(
                    float(row["wape"]),
                    6,
                ),
                "bias": round(
                    float(row["bias"]),
                    6,
                ),
                "baseline_mae": round(
                    float(row["baseline_mae"]),
                    6,
                ),
                (
                    "mae_improvement_"
                    "vs_baseline_pct"
                ): round(
                    float(
                        row[
                            "mae_improvement_"
                            "vs_baseline_pct"
                        ]
                    ),
                    4,
                ),
            }
        )

    return records


def main() -> None:
    """Run chronological backtesting for all candidate models."""
    feature_path = (
        PROCESSED_DATA_DIR
        / "weekly_forecast_features.parquet"
    )
    predictions_path = (
        MODELING_REPORTS_DIR
        / "backtest_predictions.csv"
    )
    metrics_path = (
        MODELING_REPORTS_DIR
        / "model_metrics.csv"
    )
    report_path = (
        MODELING_REPORTS_DIR
        / "model_report.json"
    )

    if not feature_path.exists():
        raise FileNotFoundError(
            "Forecast features not found. Run "
            "scripts.build_forecast_features first."
        )

    data = pd.read_parquet(feature_path)
    data["week_start"] = pd.to_datetime(
        data["week_start"]
    )

    feature_columns = [
        column
        for column in data.columns
        if column not in METADATA_COLUMNS
    ]

    predictions = backtest_models(
        data,
        feature_columns=feature_columns,
        initial_train_size=52,
        test_size=4,
        step_size=4,
    )
    metrics = summarize_metrics(
        predictions
    )

    MODELING_REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    predictions.to_csv(
        predictions_path,
        index=False,
    )
    metrics.to_csv(
        metrics_path,
        index=False,
    )

    best_models: dict[
        str,
        dict[str, object],
    ] = {}

    for product, group in metrics.groupby(
        "product",
        observed=True,
    ):
        best = group.sort_values(
            ["mae", "rmse"]
        ).iloc[0]

        best_models[str(product)] = {
            "model": str(best["model"]),
            "mae": round(
                float(best["mae"]),
                6,
            ),
            "rmse": round(
                float(best["rmse"]),
                6,
            ),
            "wape": round(
                float(best["wape"]),
                6,
            ),
            "bias": round(
                float(best["bias"]),
                6,
            ),
            (
                "mae_improvement_"
                "vs_baseline_pct"
            ): round(
                float(
                    best[
                        "mae_improvement_"
                        "vs_baseline_pct"
                    ]
                ),
                4,
            ),
        }

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "feature_path": (
            "data/processed/"
            "weekly_forecast_features.parquet"
        ),
        "forecast_horizon_weeks": 1,
        "validation": {
            "strategy": (
                "expanding-window backtesting"
            ),
            "initial_train_weeks": 52,
            "test_weeks_per_fold": 4,
            "step_weeks": 4,
            "random_split": False,
        },
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "models": [
            "naive_last_price",
            "ridge",
            "random_forest",
            "hist_gradient_boosting",
        ],
        "prediction_rows": int(
            len(predictions)
        ),
        "test_date_min": (
            predictions["week_start"]
            .min()
            .date()
            .isoformat()
        ),
        "test_date_max": (
            predictions["week_start"]
            .max()
            .date()
            .isoformat()
        ),
        "metrics": serialize_metrics(
            metrics
        ),
        "best_models": best_models,
        "metric_definitions": {
            "mae": (
                "Mean absolute error in BRL per liter."
            ),
            "rmse": (
                "Root mean squared error in BRL per liter."
            ),
            "wape": (
                "Sum of absolute errors divided by "
                "the sum of actual prices."
            ),
            "bias": (
                "Mean prediction minus actual price. "
                "Positive values indicate overprediction."
            ),
        },
    }

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Model backtesting completed.")
    print(
        metrics.to_string(
            index=False,
            float_format=lambda value: (
                f"{value:.6f}"
            ),
        )
    )
    print()
    print("Best models:")
    print(
        json.dumps(
            best_models,
            ensure_ascii=False,
            indent=2,
        )
    )
