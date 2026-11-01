import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from src.pipeline_utils import normalize_name, normalize_state
from src.spatial_integration import (
    CROSSWALK_COLUMNS,
    _load_verified_crosswalk,
    _match_summaries,
)


def _boundaries():
    return gpd.GeoDataFrame(
        {
            "boundary_fid": [1, 2, 3],
            "shapeName": ["Ludhiana", "Springfield", "Springfield"],
            "state_name": ["Punjab source label", "Haryana", "Punjab"],
        },
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 0)]),
            Polygon([(4, 0), (5, 0), (5, 1), (4, 0)]),
        ],
        crs="EPSG:4326",
    ).rename_geometry("geom")


def _assignments():
    return pd.DataFrame(
        {
            "boundary_fid": [1, 2, 3],
            "derived_state": ["Punjab", "Haryana", "Punjab"],
            "state_assignment_status": ["unique_spatial_match"] * 3,
        }
    )


def _summary(state, district):
    return {
        "state": state,
        "district": district,
        "state_key": normalize_state(state),
        "district_key": normalize_name(district),
        "total_area": 1.0,
        "total_production": 2.0,
        "crop_yield": 2.0,
        "observation_count": 1,
        "first_year": 2020,
        "last_year": 2020,
    }


def test_name_normalization_does_not_change_original_labels():
    assert normalize_name("  St. John's  ") == "STJOHNS"
    assert normalize_state("Orissa") == normalize_state("Odisha")


def test_state_conflict_ambiguous_names_and_fuzzy_candidates_stay_unmatched():
    summary = pd.DataFrame(
        [
            _summary("Punjab", "Ludhiana"),
            _summary("Haryana", "Ludhiana"),
            _summary("Delhi", "Springfield"),
            _summary("Punjab", "Ludhia"),
        ]
    )

    spatial, unmatched, matches, audit = _match_summaries(
        _boundaries(), _assignments(), summary
    )

    assert len(spatial) == 3
    assert len(matches) == 1
    assert len(unmatched) == 3
    statuses = audit.set_index(["state", "district"])["match_status"]
    assert statuses.loc[("Punjab", "Ludhiana")] == "matched_exact"
    assert statuses.loc[("Delhi", "Springfield")] == "ambiguous_district_name"
    haryana_ludhiana = audit.loc[
        audit["state"].eq("Haryana") & audit["district"].eq("Ludhiana")
    ].iloc[0]
    assert haryana_ludhiana["match_status"] == "state_mismatch_requires_review"
    typo = audit.loc[audit["district"].eq("Ludhia")].iloc[0]
    assert typo["match_status"] == "no_matching_boundary"
    assert typo["fuzzy_review_candidates"]


def test_verified_crosswalk_requires_evidence_and_unique_target(
    tmp_path, monkeypatch
):
    from src import spatial_integration

    boundaries = _boundaries()
    boundaries["derived_state"] = ["Punjab", "Haryana", "Punjab"]
    boundaries["boundary_district_key"] = boundaries["shapeName"].map(
        normalize_name
    )
    boundaries["boundary_state_key"] = boundaries["derived_state"].map(
        normalize_state
    )
    summary = pd.DataFrame([_summary("Haryana", "Ludhiana")])
    template = tmp_path / "verified_district_crosswalk.csv"
    monkeypatch.setattr(spatial_integration, "CROSSWALK_INPUT", template)

    row = {
        "original_agriculture_state": "Haryana",
        "original_agriculture_district": "Ludhiana",
        "verified_boundary_state": "Punjab",
        "verified_boundary_district": "Ludhiana",
        "matching_method": "official_source_crosswalk",
        "evidence_source": "Official district directory, URL and entry reference",
        "verification_status": "verified",
        "reviewer_notes": "",
    }
    pd.DataFrame([row], columns=CROSSWALK_COLUMNS).to_csv(
        template, index=False
    )
    verified = _load_verified_crosswalk(summary, boundaries)
    _, unmatched, matches, _ = _match_summaries(
        _boundaries(), _assignments(), summary, verified
    )
    assert len(matches) == 1
    assert matches.iloc[0]["match_status"] == "matched_verified_crosswalk"
    assert unmatched.empty

    row["evidence_source"] = ""
    pd.DataFrame([row], columns=CROSSWALK_COLUMNS).to_csv(
        template, index=False
    )
    with pytest.raises(ValueError, match="evidence_source"):
        _load_verified_crosswalk(summary, boundaries)


def test_verified_crosswalk_rejects_many_to_one_target(tmp_path, monkeypatch):
    from src import spatial_integration

    boundaries = _boundaries()
    boundaries["derived_state"] = ["Punjab", "Haryana", "Punjab"]
    boundaries["boundary_district_key"] = boundaries["shapeName"].map(
        normalize_name
    )
    boundaries["boundary_state_key"] = boundaries["derived_state"].map(
        normalize_state
    )
    summary = pd.DataFrame(
        [
            _summary("Haryana", "Ludhiana"),
            _summary("Delhi", "Ludhiana"),
        ]
    )
    template = tmp_path / "verified_district_crosswalk.csv"
    monkeypatch.setattr(spatial_integration, "CROSSWALK_INPUT", template)
    rows = []
    for state in ("Haryana", "Delhi"):
        rows.append(
            {
                "original_agriculture_state": state,
                "original_agriculture_district": "Ludhiana",
                "verified_boundary_state": "Punjab",
                "verified_boundary_district": "Ludhiana",
                "matching_method": "official_source_crosswalk",
                "evidence_source": "Official reference URL",
                "verification_status": "verified",
                "reviewer_notes": "",
            }
        )
    pd.DataFrame(rows, columns=CROSSWALK_COLUMNS).to_csv(
        template, index=False
    )
    with pytest.raises(ValueError, match="multiple source summaries"):
        _load_verified_crosswalk(summary, boundaries)


def test_name_normalization_many_to_one_matches_are_not_forced():
    summary = pd.DataFrame(
        [
            _summary("Punjab", "Ludhiana"),
            _summary("Punjab", "Ludhi-ana"),
        ]
    )

    _, unmatched, matches, audit = _match_summaries(
        _boundaries(), _assignments(), summary
    )

    assert matches.empty
    assert len(unmatched) == 2
    assert audit["match_status"].eq(
        "multiple_summaries_to_one_boundary"
    ).all()
