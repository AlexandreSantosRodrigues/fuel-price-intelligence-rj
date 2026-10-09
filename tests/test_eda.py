"""Tests for reusable exploratory-analysis transformations."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.eda import (
    build_ethanol_competitiveness,
    build_municipality_summary,
    build_weekly_price_summary,
    validate_analysis_input,
)

from src.analysis.eda import (
    build_ethanol_competitiveness,
    build_municipality_price_index,
    build_municipality_summary,
    build_weekly_price_summary,
    validate_analysis_input,
)

@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """Create a small analytical dataset with two weekly periods."""
    return pd.DataFrame(
        {
            "municipality": [
                "RIO DE JANEIRO",
                "RIO DE JANEIRO",
                "RIO DE JANEIRO",
                "RIO DE JANEIRO",
                "NITEROI",
                "NITEROI",
                "NITEROI",
                "NITEROI",
            ],
            "station_cnpj": [
                "00000000000001",
                "00000000000002",
                "00000000000001",
                "00000000000002",
                "00000000000003",
                "00000000000004",
                "00000000000003",
                "00000000000004",
            ],
            "product": [
                "GASOLINA",
                "GASOLINA",
                "ETANOL",
                "ETANOL",
                "GASOLINA",
                "GASOLINA",
                "ETANOL",
                "ETANOL",
            ],
            "collection_date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-08",
                    "2024-01-09",
                    "2024-01-08",
                    "2024-01-09",
                ]
            ),
            "sale_price": [
                6.00,
                6.20,
                4.00,
                4.20,
                5.80,
                6.00,
                4.50,
                4.40,
            ],
        }
    )


def test_validate_analysis_input_rejects_missing_columns() -> None:
    """Required analytical columns must be present."""
    incomplete = pd.DataFrame(
        {
            "municipality": ["NITEROI"],
            "sale_price": [5.99],
        }
    )

    with pytest.raises(
        ValueError,
        match="Missing required analytical columns",
    ):
        validate_analysis_input(incomplete)


def test_build_weekly_price_summary(
    sample_prices: pd.DataFrame,
) -> None:
    """Weekly aggregation must preserve product-level statistics."""
    summary = build_weekly_price_summary(sample_prices)

    gasoline = summary.loc[
        (summary["week_start"] == pd.Timestamp("2024-01-01"))
        & summary["product"].eq("GASOLINA")
    ].iloc[0]

    assert gasoline["observations"] == 2
    assert gasoline["stations"] == 2
    assert gasoline["median_price"] == pytest.approx(6.10)
    assert gasoline["mean_price"] == pytest.approx(6.10)
    assert gasoline["min_price"] == pytest.approx(6.00)
    assert gasoline["max_price"] == pytest.approx(6.20)


def test_build_municipality_summary_applies_minimum_sample(
    sample_prices: pd.DataFrame,
) -> None:
    """Municipality rankings must enforce a sample-size threshold."""
    summary = build_municipality_summary(
        sample_prices,
        min_observations=2,
    )

    assert len(summary) == 4
    assert summary["observations"].min() >= 2

    niteroi_ethanol = summary.loc[
        summary["municipality"].eq("NITEROI")
        & summary["product"].eq("ETANOL")
    ].iloc[0]

    assert niteroi_ethanol["median_price"] == pytest.approx(4.45)
    assert niteroi_ethanol["price_range"] == pytest.approx(0.10)


def test_build_ethanol_competitiveness(
    sample_prices: pd.DataFrame,
) -> None:
    """The ethanol/gasoline ratio must be calculated by city and week."""
    comparison = build_ethanol_competitiveness(sample_prices)

    rio = comparison.loc[
        comparison["municipality"].eq("RIO DE JANEIRO")
    ].iloc[0]
    niteroi = comparison.loc[
        comparison["municipality"].eq("NITEROI")
    ].iloc[0]

    assert rio["ethanol_gasoline_ratio"] == pytest.approx(
        4.10 / 6.10
    )
    assert bool(rio["ethanol_competitive"]) is True

    assert niteroi["ethanol_gasoline_ratio"] == pytest.approx(
        4.45 / 5.90
    )
    assert bool(niteroi["ethanol_competitive"]) is False

def test_build_municipality_price_index() -> None:
    """Municipalities must be compared within the same week."""
    data = pd.DataFrame(
        {
            "municipality": [
                "CITY A",
                "CITY B",
            ],
            "station_cnpj": [
                "00000000000001",
                "00000000000002",
            ],
            "product": [
                "GASOLINA",
                "GASOLINA",
            ],
            "collection_date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                ]
            ),
            "sale_price": [
                6.00,
                5.00,
            ],
        }
    )

    summary = build_municipality_price_index(
        data,
        min_observations=1,
        min_weeks=1,
    )

    city_a = summary.loc[
        summary["municipality"].eq("CITY A")
    ].iloc[0]
    city_b = summary.loc[
        summary["municipality"].eq("CITY B")
    ].iloc[0]

    assert city_a["median_relative_price"] == pytest.approx(
        6.00 / 5.50 - 1
    )
    assert city_b["median_relative_price"] == pytest.approx(
        5.00 / 5.50 - 1
    )