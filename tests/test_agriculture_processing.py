import numpy as np
import pandas as pd
import pytest

from src.process_agriculture_data import (
    aggregate_rice_records,
    parse_year,
    prepare_rice_observations,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2020", (2020, True)),
        ("2020-21", (2020, True)),
        ("2020-2021", (2020, True)),
        (" year ", (pd.NA, False)),
        (None, (pd.NA, False)),
        ("20-21", (pd.NA, False)),
    ],
)
def test_parse_year(value, expected):
    actual, valid = parse_year(value)
    if pd.isna(expected[0]):
        assert pd.isna(actual)
    else:
        assert actual == expected[0]
    assert valid is expected[1]


def _row(
    *,
    crop="Rice",
    year="2020-21",
    season="Kharif",
    area=2,
    production=10,
    district="Test District",
):
    return {
        "state": "Punjab",
        "district": district,
        "crop": crop,
        "year": year,
        "season": season,
        "area": area,
        "production": production,
        "yield": 5,
    }


def test_preparation_filters_crop_duplicates_missing_years_and_bad_area():
    raw = pd.DataFrame(
        [
            _row(),
            _row(),
            _row(year="2021", season="Rabi", area=3, production=12),
            _row(year="2021", season="Missing Production", production=None),
            _row(year="year", season="Invalid Year"),
            _row(year=None, season="Missing Year"),
            _row(year="2021", season="Zero Area", area=0, production=5),
            _row(crop="Wheat", season="Other Crop"),
        ]
    )

    rice_raw, rice_unique, _, valid, counts = prepare_rice_observations(raw)

    assert len(rice_raw) == 7
    assert len(rice_unique) == 6
    assert len(valid) == 2
    assert counts["rice_invalid_year_count"] == 1
    assert counts["rice_missing_year_count"] == 1
    assert counts["missing_production_count"] == 1
    assert counts["invalid_numeric_count"] == 1
    assert counts["all_crop_invalid_year_count"] == 1


def test_yield_uses_aggregated_totals_not_mean_of_row_yields():
    raw = pd.DataFrame(
        [
            _row(area=2, production=10),
            _row(year="2021", season="Rabi", area=3, production=12),
        ]
    )
    _, _, _, valid, _ = prepare_rice_observations(raw)

    district_summary, state_summary = aggregate_rice_records(valid)

    assert district_summary.loc[0, "total_area"] == 5
    assert district_summary.loc[0, "total_production"] == 22
    assert district_summary.loc[0, "crop_yield"] == pytest.approx(22 / 5)
    assert state_summary.loc[0, "average_yield"] == pytest.approx(22 / 5)
    assert district_summary.loc[0, "crop_yield"] != pytest.approx(
        np.mean([10 / 2, 12 / 3])
    )
