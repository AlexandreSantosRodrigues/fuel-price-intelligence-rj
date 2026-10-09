"""Build the leakage-safe weekly forecasting feature dataset."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.analysis.eda import (
    build_weekly_price_summary,
)
from src.features.forecast import (
    build_forecast_features,
    regularize_weekly_series,
)
from src.settings import (
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
)

FEATURE_REPORTS_DIR = REPORTS_DIR / "features"


def main() -> None:
    """Generate the modeling table and its quality report."""
    input_path = (
        PROCESSED_DATA_DIR
        / "rj_fuel_prices.parquet"
    )
    output_path = (
        PROCESSED_DATA_DIR
        / "weekly_forecast_features.parquet"
    )
    report_path = (
        FEATURE_REPORTS_DIR
        / "feature_report.json"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {input_path}"
        )

    prices = pd.read_parquet(input_path)
    weekly = build_weekly_price_summary(prices)

    regularized = regularize_weekly_series(
        weekly,
        min_coverage_ratio=0.50,
    )
    features = build_forecast_features(
        weekly,
        lags=(1, 2, 4, 8, 12),
        rolling_windows=(4, 8, 12),
        min_coverage_ratio=0.50,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    FEATURE_REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    features.to_parquet(
        output_path,
        index=False,
        engine="pyarrow",
    )

    metadata_columns = {
        "week_start",
        "product",
        "target_price",
        "observations",
        "stations",
        "coverage_ratio",
    }
    feature_columns = [
        column
        for column in features.columns
        if column not in metadata_columns
    ]

    product_rows = {
        str(product): int(len(group))
        for product, group in features.groupby(
            "product",
            observed=True,
        )
    }

    unreliable_observed_rows = int(
        (
            regularized["is_observed"]
            & ~regularized["is_reliable_target"]
        ).sum()
    )
    missing_calendar_rows = int(
        (~regularized["is_observed"]).sum()
    )

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "input_path": (
            "data/processed/"
            "rj_fuel_prices.parquet"
        ),
        "output_path": (
            "data/processed/"
            "weekly_forecast_features.parquet"
        ),
        "forecast_horizon_weeks": 1,
        "target": (
            "weekly statewide median sale price"
        ),
        "minimum_coverage_ratio": 0.50,
        "raw_price_rows": int(len(prices)),
        "observed_weekly_rows": int(len(weekly)),
        "regularized_weekly_rows": int(
            len(regularized)
        ),
        "missing_calendar_rows": (
            missing_calendar_rows
        ),
        "unreliable_observed_rows": (
            unreliable_observed_rows
        ),
        "modeling_rows": int(len(features)),
        "modeling_rows_by_product": product_rows,
        "date_min": (
            features["week_start"]
            .min()
            .date()
            .isoformat()
        ),
        "date_max": (
            features["week_start"]
            .max()
            .date()
            .isoformat()
        ),
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "leakage_controls": [
            (
                "All lag and rolling features use only "
                "values available before the target week."
            ),
            (
                "Missing weeks are filled only in the "
                "historical predictor series using "
                "forward filling."
            ),
            (
                "Missing weeks and observations below "
                "50% of the typical weekly coverage "
                "are excluded as targets."
            ),
            (
                "Chronological validation must be used; "
                "random train-test splitting is forbidden."
            ),
        ],
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

    print("Forecast feature engineering completed.")
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()