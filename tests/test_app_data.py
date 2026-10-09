"""Tests for the Streamlit dashboard data layer."""

from pathlib import Path

import pandas as pd
import pytest

from src.app.data import (
    build_current_snapshot,
    build_municipality_ranking,
    build_model_comparison,
    load_dashboard_data,
)


@pytest.fixture
def report_files(tmp_path: Path) -> dict[str, Path]:
    """Create representative report files for dashboard tests."""
    weekly = pd.DataFrame(
        {
            "week_start": [
                "2026-09-21",
                "2026-09-21",
                "2026-09-28",
                "2026-09-28",
            ],
            "product": [
                "ETANOL",
                "GASOLINA",
                "ETANOL",
                "GASOLINA",
            ],
            "observations": [300, 330, 310, 340],
            "stations": [300, 330, 310, 340],
            "mean_price": [4.80, 6.50, 4.85, 6.60],
            "median_price": [4.79, 6.49, 4.84, 6.59],
            "min_price": [4.20, 5.80, 4.25, 5.90],
            "max_price": [5.50, 7.20, 5.60, 7.30],
            "std_price": [0.30, 0.35, 0.31, 0.36],
            "q1_price": [4.60, 6.30, 4.65, 6.40],
            "q3_price": [5.00, 6.80, 5.05, 6.90],
            "price_range": [1.30, 1.40, 1.35, 1.40],
            "iqr_price": [0.40, 0.50, 0.40, 0.50],
        }
    )

    competitiveness = pd.DataFrame(
        {
            "municipality": [
                "NITEROI",
                "RIO DE JANEIRO",
            ],
            "week_start": [
                "2026-09-28",
                "2026-09-28",
            ],
            "gasoline_median": [6.70, 6.59],
            "ethanol_median": [4.60, 4.84],
            "ethanol_gasoline_ratio": [0.6866, 0.7344],
            "ethanol_competitive": [True, False],
        }
    )

    municipality = pd.DataFrame(
        {
            "municipality": [
                "NITEROI",
                "TRES RIOS",
                "TERESOPOLIS",
            ],
            "product": [
                "GASOLINA",
                "GASOLINA",
                "GASOLINA",
            ],
            "observations": [1000, 700, 170],
            "weeks": [139, 139, 26],
            "median_price": [6.10, 6.69, 5.49],
            "median_relative_price": [
                -0.046,
                0.096,
                -0.050,
            ],
            "mean_relative_price": [
                -0.045,
                0.095,
                -0.049,
            ],
            "stations": [56, 30, 25],
            "median_relative_price_pct": [
                -4.60,
                9.60,
                -5.00,
            ],
        }
    )

    metrics = pd.DataFrame(
        {
            "product": [
                "ETANOL",
                "ETANOL",
                "GASOLINA",
                "GASOLINA",
            ],
            "model": [
                "naive_last_price",
                "ridge",
                "naive_last_price",
                "ridge",
            ],
            "predictions": [76, 76, 76, 76],
            "folds": [19, 19, 19, 19],
            "mae": [0.0318, 0.0518, 0.0301, 0.0494],
            "rmse": [0.0506, 0.0728, 0.0645, 0.0812],
            "wape": [0.0068, 0.0110, 0.0048, 0.0079],
            "bias": [-0.0020, 0.0099, -0.0053, 0.0048],
            "baseline_mae": [
                0.0318,
                0.0318,
                0.0301,
                0.0301,
            ],
            "mae_improvement_vs_baseline_pct": [
                0.0,
                -62.6,
                0.0,
                -63.8,
            ],
        }
    )

    paths = {
        "weekly": tmp_path / "weekly.csv",
        "competitiveness": tmp_path / "competitiveness.csv",
        "municipality": tmp_path / "municipality.csv",
        "metrics": tmp_path / "metrics.csv",
    }

    weekly.to_csv(paths["weekly"], index=False)
    competitiveness.to_csv(
        paths["competitiveness"],
        index=False,
    )
    municipality.to_csv(
        paths["municipality"],
        index=False,
    )
    metrics.to_csv(paths["metrics"], index=False)

    return paths


def test_load_dashboard_data_parses_dates(
    report_files: dict[str, Path],
) -> None:
    """Load all versioned reports and parse their date columns."""
    data = load_dashboard_data(
        weekly_path=report_files["weekly"],
        competitiveness_path=report_files[
            "competitiveness"
        ],
        municipality_path=report_files["municipality"],
        metrics_path=report_files["metrics"],
    )

    assert set(data) == {
        "weekly",
        "competitiveness",
        "municipality",
        "metrics",
    }
    assert pd.api.types.is_datetime64_any_dtype(
        data["weekly"]["week_start"]
    )
    assert pd.api.types.is_datetime64_any_dtype(
        data["competitiveness"]["week_start"]
    )


def test_build_current_snapshot_uses_latest_week(
    report_files: dict[str, Path],
) -> None:
    """Create current prices and transparent baseline forecasts."""
    data = load_dashboard_data(
        weekly_path=report_files["weekly"],
        competitiveness_path=report_files[
            "competitiveness"
        ],
        municipality_path=report_files["municipality"],
        metrics_path=report_files["metrics"],
    )

    snapshot = build_current_snapshot(data["weekly"])

    assert len(snapshot) == 2
    assert snapshot["week_start"].nunique() == 1
    assert snapshot["week_start"].iloc[0] == pd.Timestamp(
        "2026-09-28"
    )
    assert set(snapshot["product"]) == {
        "ETANOL",
        "GASOLINA",
    }
    assert snapshot.loc[
        snapshot["product"].eq("ETANOL"),
        "forecast_next_week",
    ].iloc[0] == pytest.approx(4.84)
    assert snapshot.loc[
        snapshot["product"].eq("GASOLINA"),
        "forecast_next_week",
    ].iloc[0] == pytest.approx(6.59)
    assert snapshot["forecast_week"].nunique() == 1
    assert snapshot["forecast_week"].iloc[0] == pd.Timestamp(
        "2026-10-05"
    )


def test_build_model_comparison_ranks_by_mae(
    report_files: dict[str, Path],
) -> None:
    """Rank the evaluated approaches independently by product."""
    data = load_dashboard_data(
        weekly_path=report_files["weekly"],
        competitiveness_path=report_files[
            "competitiveness"
        ],
        municipality_path=report_files["municipality"],
        metrics_path=report_files["metrics"],
    )

    comparison = build_model_comparison(data["metrics"])

    winners = comparison.loc[
        comparison["rank"].eq(1),
        ["product", "model"],
    ]

    assert winners.to_dict("records") == [
        {
            "product": "ETANOL",
            "model": "naive_last_price",
        },
        {
            "product": "GASOLINA",
            "model": "naive_last_price",
        },
    ]


def test_build_municipality_ranking_filters_product(
    report_files: dict[str, Path],
) -> None:
    """Return municipalities ordered by adjusted relative price."""
    data = load_dashboard_data(
        weekly_path=report_files["weekly"],
        competitiveness_path=report_files[
            "competitiveness"
        ],
        municipality_path=report_files["municipality"],
        metrics_path=report_files["metrics"],
    )

    ranking = build_municipality_ranking(
        data["municipality"],
        product="GASOLINA",
    )

    assert ranking["municipality"].tolist() == [
        "TERESOPOLIS",
        "NITEROI",
        "TRES RIOS",
    ]
    assert ranking[
        "median_relative_price_pct"
    ].is_monotonic_increasing