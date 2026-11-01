"""Calculate and export district- and state-level spatial analysis products."""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from sqlalchemy import text

from src.pipeline_utils import (
    CSV_OUTPUT,
    SPATIAL_TABLE,
    create_database_engine,
    ensure_output_directories,
)


LOGGER = logging.getLogger("agri_gis.stage4")
AREA_CRS = "EPSG:6933"


def load_spatial_result() -> gpd.GeoDataFrame:
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            spatial = gpd.read_postgis(
                text("SELECT * FROM public.rice_district_spatial ORDER BY boundary_fid"),
                connection,
                geom_col="geom",
            )
    finally:
        engine.dispose()
    if spatial.empty:
        raise ValueError(f"{SPATIAL_TABLE} contains no spatial records.")
    if spatial.crs is None or spatial.crs.to_epsg() != 4326:
        raise ValueError(
            f"{SPATIAL_TABLE} must use EPSG:4326; found {spatial.crs!s}."
        )
    return spatial


def run_spatial_analysis(
    spatial: gpd.GeoDataFrame | None = None,
    district_summary: pd.DataFrame | None = None,
    state_summary: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame | gpd.GeoDataFrame]:
    ensure_output_directories()
    if spatial is None:
        spatial = load_spatial_result()
    if district_summary is None:
        district_summary = pd.read_csv(CSV_OUTPUT / "district_rice_summary.csv")
    if state_summary is None:
        state_summary = pd.read_csv(CSV_OUTPUT / "state_rice_summary.csv")
    if len(spatial) != 735:
        raise ValueError(f"Expected 735 district polygons; found {len(spatial)}.")
    if spatial.geometry.isna().any() or spatial.geometry.is_empty.any():
        raise ValueError("Spatial analysis input has missing or empty geometries.")
    if not shapely.is_valid(spatial.geometry.array).all():
        raise ValueError("Spatial analysis input contains invalid geometries.")

    projected = spatial.to_crs(AREA_CRS)
    spatial_summary = spatial.drop(columns="geom").copy()
    spatial_summary["boundary_area_km2"] = projected.geometry.area / 1_000_000
    valid_geometry_areas = np.isfinite(spatial_summary["boundary_area_km2"])
    if not valid_geometry_areas.all():
        raise ValueError("Projected district area calculation returned non-finite values.")

    rice = spatial_summary[
        spatial_summary["total_production"].notna()
        & spatial_summary["total_area"].notna()
        & spatial_summary["crop_yield"].notna()
    ].copy()
    if rice.empty:
        raise ValueError("No districts have valid joined Rice statistics.")

    if district_summary.empty:
        raise ValueError("District Rice summary is empty.")
    if state_summary.empty:
        raise ValueError("State Rice summary is empty.")

    top_production = (
        district_summary.sort_values(
            ["total_production", "district", "state"],
            ascending=[False, True, True],
        )
        .head(10)[
            [
                "district",
                "state",
                "total_area",
                "total_production",
                "crop_yield",
                "observation_count",
            ]
        ]
        .reset_index(drop=True)
    )
    top_yield = (
        district_summary.dropna(subset=["crop_yield"]).sort_values(
            ["crop_yield", "district", "state"],
            ascending=[False, True, True],
        )
        .head(10)[
            [
                "district",
                "state",
                "total_area",
                "total_production",
                "crop_yield",
                "observation_count",
            ]
        ]
        .reset_index(drop=True)
    )

    state_stats = state_summary.copy()
    if "average_yield" not in state_stats:
        state_stats["average_yield"] = np.divide(
            state_stats["total_production"],
            state_stats["total_area"],
            out=np.full(len(state_stats), np.nan, dtype=float),
            where=state_stats["total_area"].to_numpy() > 0,
        )
    state_stats = state_stats.sort_values(
        "total_production", ascending=False
    )

    matched_lookup = rice[
        [
            "agriculture_state",
            "agriculture_district",
            "boundary_area_km2",
            "match_status",
            "match_method",
        ]
    ].rename(
        columns={
            "agriculture_state": "state",
            "agriculture_district": "district",
        }
    )
    yield_distribution = district_summary.merge(
        matched_lookup,
        on=["state", "district"],
        how="left",
        validate="one_to_one",
    )
    yield_distribution["match_status"] = yield_distribution[
        "match_status"
    ].fillna("unmatched")
    yield_distribution["match_method"] = yield_distribution[
        "match_method"
    ].fillna("no reliable boundary match")
    yield_distribution = yield_distribution.sort_values(["state", "district"])
    area_production = district_summary[
        [
            "district",
            "state",
            "total_area",
            "total_production",
            "crop_yield",
            "observation_count",
        ]
    ].sort_values("total_area", ascending=False)
    unmatched = pd.read_csv(CSV_OUTPUT / "unmatched_rice_districts.csv")
    missing_analysis = pd.DataFrame(
        [
            ("boundary_feature_count", len(spatial)),
            ("districts_with_rice_statistics", int(spatial["crop_yield"].notna().sum())),
            ("districts_without_rice_statistics", len(spatial) - len(rice)),
            ("agriculture_district_summary_count", len(district_summary)),
            ("unmatched_agriculture_summaries", len(unmatched)),
            (
                "ambiguous_agriculture_summaries",
                int(
                    unmatched["match_status"]
                    .isin(
                        [
                            "ambiguous_state_district_key",
                            "ambiguous_district_name",
                        ]
                    )
                    .sum()
                ),
            ),
            (
                "state_mismatch_requires_review",
                int(
                    unmatched["match_status"]
                    .eq("state_mismatch_requires_review")
                    .sum()
                ),
            ),
            (
                "districts_without_yield",
                int(spatial["crop_yield"].isna().sum()),
            ),
            (
                "boundary_state_assignment_issues",
                int(
                    spatial["state_assignment_status"]
                    .ne("unique_spatial_match")
                    .sum()
                ),
            ),
        ],
        columns=["metric", "value"],
    )

    outputs: dict[str, pd.DataFrame] = {
        "top_10_rice_production": top_production,
        "top_10_rice_yield": top_yield,
        "state_rice_analysis": state_stats,
        "rice_area_production_comparison": area_production,
        "rice_yield_distribution": yield_distribution,
        "rice_missing_unmatched_analysis": missing_analysis,
    }
    for name, frame in outputs.items():
        frame.to_csv(CSV_OUTPUT / f"{name}.csv", index=False)
    spatial_summary.drop(columns="geom", errors="ignore").to_csv(
        CSV_OUTPUT / "rice_spatial_distribution.csv", index=False
    )

    LOGGER.info(
        "Spatial analysis complete: %d districts with Rice metrics, "
        "%d without metrics; area measured in %s.",
        len(rice),
        len(spatial) - len(rice),
        AREA_CRS,
    )
    return {
        **outputs,
        "spatial_distribution": spatial,
        "projected_spatial": projected,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_spatial_analysis()
