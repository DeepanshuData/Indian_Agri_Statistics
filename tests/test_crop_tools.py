import pandas as pd
import pytest

from app.profitability_engine import calculate_profitability
from app.recommendation_engine import get_historical_crop_summary


def _record(state, district, crop, area, production, year="2020", season="Kharif"):
    return {
        "state": state,
        "district": district,
        "crop": crop,
        "area": area,
        "production": production,
        "year": year,
        "season": season,
    }


def test_historical_crop_summary_aggregates_and_filters_source_records():
    records = pd.DataFrame(
        [
            _record("Punjab", "Amritsar", "Rice", 2, 10),
            _record("Punjab", "Amritsar", "Rice", 3, 12, "2021"),
            _record("Punjab", "Amritsar", "Wheat", 3, 15),
            _record("Haryana", "Amritsar", "Maize", 2, 100),
            _record("Punjab", "Amritsar", "Rice", 1, 100, "year"),
            _record("Punjab", "Amritsar", "Rice", 0, 100, "2022"),
            _record("Punjab", "Amritsar", "Rice", 1, None, "2022"),
            _record("Punjab", "Amritsar", "Rice", 1, 50, "2022", "Rabi"),
        ]
    )

    summary = get_historical_crop_summary(
        records, "punjab", "AMRITSAR", "kharif"
    )

    rice = summary.loc[summary["crop"] == "Rice"].iloc[0]
    assert rice["total_area"] == 5
    assert rice["total_production"] == 22
    assert rice["historical_yield"] == pytest.approx(22 / 5)
    assert rice["observations"] == 2
    assert rice["years_of_history"] == 2
    assert "Maize" not in set(summary["crop"])


def test_profitability_uses_user_entered_kilograms_without_unit_conversion():
    economics = pd.DataFrame(
        [
            {
                "crop": "Rice",
                "cost_per_acre": 1000,
                "price_per_kg": 10,
                "price_volatility": 0.2,
                "water_requirement": "High",
            }
        ]
    )

    result = calculate_profitability("Rice", 2, 500, economics)

    assert result["Expected Production (kg)"] == 500
    assert result["Expected Revenue"] == 5000
    assert result["Estimated Cost"] == 2000
    assert result["Expected Profit"] == 3000
    assert result["ROI (%)"] == 150


def test_profitability_rejects_negative_user_inputs():
    economics = pd.DataFrame(
        [
            {
                "crop": "Rice",
                "cost_per_acre": 1000,
                "price_per_kg": 10,
                "price_volatility": 0.2,
                "water_requirement": "High",
            }
        ]
    )

    with pytest.raises(ValueError, match="non-negative"):
        calculate_profitability("Rice", 1, -1, economics)
