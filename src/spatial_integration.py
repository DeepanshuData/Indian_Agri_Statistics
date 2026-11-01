"""Join Rice summaries to district boundaries and persist the spatial result."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from uuid import uuid4

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.pipeline_utils import (
    AREA_UNITS,
    BOUNDARY_TABLE,
    CSV_OUTPUT,
    PRODUCTION_UNITS,
    PROJECT_ROOT,
    SPATIAL_TABLE,
    create_database_engine,
    ensure_output_directories,
    normalize_name,
    normalize_state,
)


LOGGER = logging.getLogger("agri_gis.stage3")
OWNERSHIP_COMMENT = "agri-gis-pipeline:v1:rice_district_spatial"
LEGACY_REFERENCE_TABLE = "public.indian_districts"
CROSSWALK_INPUT = PROJECT_ROOT / "config" / "verified_district_crosswalk.csv"
CROSSWALK_COLUMNS = [
    "original_agriculture_state",
    "original_agriculture_district",
    "verified_boundary_state",
    "verified_boundary_district",
    "matching_method",
    "evidence_source",
    "verification_status",
    "reviewer_notes",
]


def _load_verified_crosswalk(
    district_summary: pd.DataFrame,
    boundaries: gpd.GeoDataFrame,
) -> pd.DataFrame:
    if not CROSSWALK_INPUT.is_file():
        raise FileNotFoundError(
            f"District crosswalk template is missing: {CROSSWALK_INPUT}"
        )
    crosswalk = pd.read_csv(
        CROSSWALK_INPUT,
        dtype="string",
        keep_default_na=False,
    )
    missing_columns = set(CROSSWALK_COLUMNS).difference(crosswalk.columns)
    if missing_columns:
        raise ValueError(
            "District crosswalk is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    crosswalk = crosswalk[CROSSWALK_COLUMNS].copy()
    crosswalk["verification_status"] = (
        crosswalk["verification_status"].str.strip().str.casefold()
    )
    invalid_statuses = set(crosswalk["verification_status"]) - {
        "",
        "pending",
        "verified",
    }
    if invalid_statuses:
        raise ValueError(
            "Crosswalk verification_status must be blank, pending, or verified; "
            f"found {sorted(invalid_statuses)}."
        )
    verified = crosswalk[
        crosswalk["verification_status"].eq("verified")
    ].copy()
    if verified.empty:
        return verified.assign(
            source_state_key=pd.Series(dtype="string"),
            source_district_key=pd.Series(dtype="string"),
            target_state_key=pd.Series(dtype="string"),
            target_district_key=pd.Series(dtype="string"),
        )

    required_values = [
        "original_agriculture_state",
        "original_agriculture_district",
        "verified_boundary_state",
        "verified_boundary_district",
        "matching_method",
        "evidence_source",
    ]
    for column in required_values:
        verified[column] = verified[column].str.strip()
        if verified[column].eq("").any():
            raise ValueError(
                f"Verified crosswalk rows must provide {column!r}."
            )

    verified["source_state_key"] = verified[
        "original_agriculture_state"
    ].map(normalize_state)
    verified["source_district_key"] = verified[
        "original_agriculture_district"
    ].map(normalize_name)
    verified["target_state_key"] = verified[
        "verified_boundary_state"
    ].map(normalize_state)
    verified["target_district_key"] = verified[
        "verified_boundary_district"
    ].map(normalize_name)

    source_keys = set(
        zip(district_summary["state_key"], district_summary["district_key"])
    )
    boundary_keys = boundaries.groupby(
        ["boundary_state_key", "boundary_district_key"], dropna=False
    ).size()
    for row in verified.itertuples(index=False):
        source_key = (row.source_state_key, row.source_district_key)
        if source_key not in source_keys:
            raise ValueError(
                "Verified crosswalk source does not identify an agriculture "
                f"summary: {row.original_agriculture_state} / "
                f"{row.original_agriculture_district}."
            )
        target_key = (row.target_state_key, row.target_district_key)
        if boundary_keys.get(target_key, 0) != 1:
            raise ValueError(
                "Verified crosswalk target must identify exactly one boundary: "
                f"{row.verified_boundary_state} / "
                f"{row.verified_boundary_district}."
            )
    if verified.duplicated(
        ["source_state_key", "source_district_key"]
    ).any():
        raise ValueError("Verified crosswalk has duplicate agriculture keys.")
    if verified.duplicated(
        ["target_state_key", "target_district_key"]
    ).any():
        raise ValueError(
            "Verified crosswalk maps multiple source summaries to one boundary."
        )
    return verified


def _fuzzy_boundary_candidates(
    district_key: str,
    boundaries: gpd.GeoDataFrame,
    *,
    limit: int = 3,
    minimum_score: float = 0.75,
) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for row in boundaries.itertuples(index=False):
        if not row.boundary_district_key:
            continue
        score = SequenceMatcher(
            None, district_key, row.boundary_district_key
        ).ratio()
        if score >= minimum_score:
            label = (
                f"{row.derived_state} | {row.shapeName} "
                f"(similarity={score:.2f})"
            )
            candidates.append((score, label))
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
    return [label for _, label in candidates[:limit]]


def _read_spatial_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            boundaries = gpd.read_postgis(
                """
                SELECT ROW_NUMBER() OVER (
                           ORDER BY "state_name", "shapeName", "shapeID"
                       )::integer AS boundary_fid,
                       geom, "shapeName", "state_name",
                       "shapeISO", "shapeID", "shapeGroup", "shapeType",
                       sample_crop_area_ha, id, objectid, state, stcode,
                       shape_leng, shape_area, ds_name, src_agency, join_key
                FROM public.district_boundaries
                ORDER BY "state_name", "shapeName", "shapeID"
                """,
                connection,
                geom_col="geom",
            )
            legacy = gpd.read_postgis(
                """
                SELECT gid, geom, statename, distname
                FROM public.indian_districts
                ORDER BY gid
                """,
                connection,
                geom_col="geom",
            )
    finally:
        engine.dispose()
    if boundaries.empty:
        raise ValueError(f"{BOUNDARY_TABLE} contains no district features.")
    if legacy.empty:
        raise ValueError(
            f"{LEGACY_REFERENCE_TABLE} is empty; cannot derive spatial states."
        )
    if boundaries.crs is None or boundaries.crs.to_epsg() != 4326:
        raise ValueError(
            f"{BOUNDARY_TABLE} must use EPSG:4326; found {boundaries.crs!s}."
        )
    if legacy.crs is None or legacy.crs.to_epsg() != 4326:
        raise ValueError(
            f"{LEGACY_REFERENCE_TABLE} must use EPSG:4326; found {legacy.crs!s}."
        )
    return boundaries, legacy


def _derive_spatial_states(
    boundaries: gpd.GeoDataFrame,
    legacy: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    points = boundaries[["boundary_fid", "geom"]].copy()
    points.geometry = boundaries.geometry.representative_point()
    joined = gpd.sjoin(
        points,
        legacy[["statename", "geom"]].rename_geometry("geometry"),
        how="left",
        predicate="within",
    )
    assignments: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    legacy_states = joined.groupby("boundary_fid", dropna=False)["statename"].agg(
        lambda values: sorted({str(value) for value in values.dropna()})
    )

    for boundary in boundaries.itertuples(index=False):
        candidates = legacy_states.get(boundary.boundary_fid, [])
        if len(candidates) == 1:
            assignments.append(
                {
                    "boundary_fid": boundary.boundary_fid,
                    "derived_state": candidates[0],
                    "state_assignment_status": "unique_spatial_match",
                }
            )
        else:
            status = "no_spatial_match" if not candidates else "ambiguous_spatial_match"
            assignments.append(
                {
                    "boundary_fid": boundary.boundary_fid,
                    "derived_state": pd.NA,
                    "state_assignment_status": status,
                }
            )
            issues.append(
                {
                    "boundary_fid": boundary.boundary_fid,
                    "district": boundary.shapeName,
                    "source_state_label": boundary.state_name,
                    "candidate_reference_states": "|".join(candidates),
                    "issue": status,
                }
            )

    assignment_frame = pd.DataFrame(assignments)
    issue_frame = pd.DataFrame(
        issues,
        columns=[
            "boundary_fid",
            "district",
            "source_state_label",
            "candidate_reference_states",
            "issue",
        ],
    )
    return assignment_frame, issue_frame


def _match_summaries(
    boundaries: gpd.GeoDataFrame,
    assignments: pd.DataFrame,
    district_summary: pd.DataFrame,
    verified_crosswalk: pd.DataFrame | None = None,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    boundary_frame = boundaries.merge(
        assignments, on="boundary_fid", validate="one_to_one"
    )
    boundary_frame["boundary_district_key"] = boundary_frame["shapeName"].map(
        normalize_name
    )
    boundary_frame["boundary_state_key"] = boundary_frame["derived_state"].map(
        normalize_state
    )
    boundary_frame["join_state_key"] = (
        boundary_frame["boundary_state_key"].fillna("")
    )

    boundary_key_lookup: dict[tuple[str, str], list[int]] = {}
    for row in boundary_frame.itertuples():
        if row.boundary_state_key and row.boundary_district_key:
            boundary_key_lookup.setdefault(
                (row.boundary_state_key, row.boundary_district_key), []
            ).append(row.boundary_fid)
    district_lookup: dict[str, list[int]] = {}
    for row in boundary_frame.itertuples():
        if row.boundary_district_key:
            district_lookup.setdefault(row.boundary_district_key, []).append(
                row.boundary_fid
            )

    crosswalk_lookup: dict[tuple[str, str], object] = {}
    if verified_crosswalk is not None:
        crosswalk_lookup = {
            (row.source_state_key, row.source_district_key): row
            for row in verified_crosswalk.itertuples(index=False)
        }

    audit_rows: list[dict[str, object]] = []
    chosen: list[dict[str, object]] = []
    mapping_counts: dict[int, int] = {}
    boundary_by_id = boundary_frame.set_index("boundary_fid")
    for row in district_summary.itertuples(index=False):
        district_key = row.district_key or normalize_name(row.district)
        state_key = row.state_key or normalize_state(row.state)
        source_key = (state_key, district_key)
        exact_candidates = boundary_key_lookup.get(source_key, [])
        crosswalk_row = crosswalk_lookup.get(source_key)
        candidate_ids: list[int] = []
        fuzzy_candidates: list[str] = []
        evidence_source = ""
        if len(exact_candidates) == 1:
            boundary_id = exact_candidates[0]
            method = "normalized_state_and_district"
            status = "matched_exact"
        elif crosswalk_row is not None:
            target_key = (
                crosswalk_row.target_state_key,
                crosswalk_row.target_district_key,
            )
            boundary_id = boundary_key_lookup[target_key][0]
            method = crosswalk_row.matching_method
            evidence_source = crosswalk_row.evidence_source
            status = "matched_verified_crosswalk"
        else:
            if len(exact_candidates) > 1:
                candidate_ids = exact_candidates
                status = "ambiguous_state_district_key"
            else:
                candidate_ids = district_lookup.get(district_key, [])
                if len(candidate_ids) > 1:
                    status = "ambiguous_district_name"
                elif len(candidate_ids) == 1:
                    status = "state_mismatch_requires_review"
                else:
                    status = "no_matching_boundary"
                    fuzzy_candidates = _fuzzy_boundary_candidates(
                        district_key, boundary_frame
                    )

        candidate_labels = [
            f"{boundary_by_id.loc[boundary_id, 'derived_state']} | "
            f"{boundary_by_id.loc[boundary_id, 'shapeName']}"
            for boundary_id in candidate_ids
        ]
        if status in {"matched_exact", "matched_verified_crosswalk"}:
            matched_boundary = boundary_by_id.loc[boundary_id]
            candidate_ids = [boundary_id]
            candidate_labels = [
                f"{matched_boundary['derived_state']} | "
                f"{matched_boundary['shapeName']}"
            ]
            chosen.append(
                {
                    "boundary_fid": boundary_id,
                    "agriculture_state": row.state,
                    "agriculture_district": row.district,
                    "total_area": row.total_area,
                    "total_production": row.total_production,
                    "crop_yield": row.crop_yield,
                    "area_units": AREA_UNITS,
                    "production_units": PRODUCTION_UNITS,
                    "yield_units": (
                        "source production unit / source area unit (unverified)"
                    ),
                    "observation_count": row.observation_count,
                    "first_year": row.first_year,
                    "last_year": row.last_year,
                    "match_method": method,
                    "match_status": status,
                    "evidence_source": evidence_source,
                    "_audit_index": len(audit_rows),
                }
            )
            mapping_counts[boundary_id] = mapping_counts.get(boundary_id, 0) + 1

        audit_rows.append(
            {
                "state": row.state,
                "district": row.district,
                "state_key": state_key,
                "district_key": district_key,
                "total_area": row.total_area,
                "total_production": row.total_production,
                "crop_yield": row.crop_yield,
                "area_units": AREA_UNITS,
                "production_units": PRODUCTION_UNITS,
                "yield_units": (
                    "source production unit / source area unit (unverified)"
                ),
                "match_status": status,
                "match_method": method if status.startswith("matched_") else "",
                "candidate_boundary_count": len(candidate_ids),
                "candidate_boundaries": "; ".join(candidate_labels),
                "fuzzy_review_candidates": "; ".join(fuzzy_candidates),
                "matched_boundary_state": (
                    str(matched_boundary["derived_state"])
                    if status in {"matched_exact", "matched_verified_crosswalk"}
                    else ""
                ),
                "matched_boundary_district": (
                    str(matched_boundary["shapeName"])
                    if status in {"matched_exact", "matched_verified_crosswalk"}
                    else ""
                ),
                "evidence_source": evidence_source,
                "area_units": AREA_UNITS,
                "production_units": PRODUCTION_UNITS,
                "yield_units": (
                    "source production unit / source area unit (unverified)"
                ),
            }
        )

    duplicated_targets = {
        boundary_id
        for boundary_id, count in mapping_counts.items()
        if count > 1
    }
    for row in chosen:
        if row["boundary_fid"] in duplicated_targets:
            audit_rows[row["_audit_index"]]["match_status"] = (
                "multiple_summaries_to_one_boundary"
            )
            audit_rows[row["_audit_index"]]["match_method"] = ""
            audit_rows[row["_audit_index"]]["matched_boundary_state"] = ""
            audit_rows[row["_audit_index"]]["matched_boundary_district"] = ""
    chosen = [
        row for row in chosen if row["boundary_fid"] not in duplicated_targets
    ]

    match_frame = pd.DataFrame(
        chosen,
        columns=[
            "boundary_fid",
            "agriculture_state",
            "agriculture_district",
            "total_area",
            "total_production",
            "crop_yield",
            "observation_count",
            "first_year",
            "last_year",
            "match_method",
            "match_status",
            "evidence_source",
        ],
    ).drop(columns="_audit_index", errors="ignore")
    spatial = boundary_frame.merge(
        match_frame, on="boundary_fid", how="left", validate="one_to_one"
    )
    spatial["district"] = spatial["shapeName"]
    spatial["state"] = spatial["derived_state"]
    spatial["match_status"] = spatial["match_status"].fillna(
        "no_matching_agriculture_summary"
    )
    audit_frame = pd.DataFrame(audit_rows)
    unmatched_frame = audit_frame[
        ~audit_frame["match_status"].isin(
            ["matched_exact", "matched_verified_crosswalk"]
        )
    ].copy()
    return spatial, unmatched_frame, match_frame, audit_frame


def _validate_spatial_result(spatial: gpd.GeoDataFrame) -> None:
    if len(spatial) != 735:
        raise ValueError(
            f"Expected all 735 boundaries in spatial result; got {len(spatial)}."
        )
    if spatial["boundary_fid"].duplicated().any():
        raise ValueError("Spatial output has duplicate boundary identifiers.")
    if spatial.geometry.isna().any() or spatial.geometry.is_empty.any():
        raise ValueError("Spatial output has missing or empty geometries.")
    if (~spatial.geometry.is_valid).any():
        raise ValueError("Spatial output contains invalid geometries.")
    if spatial.crs is None or spatial.crs.to_epsg() != 4326:
        raise ValueError(f"Spatial output CRS must be EPSG:4326, got {spatial.crs}.")


def _persist_spatial_table(
    spatial: gpd.GeoDataFrame,
    *,
    refresh_owned_table: bool = True,
) -> None:
    engine = create_database_engine()
    staging_table = f"rice_district_spatial_load_{uuid4().hex[:10]}"
    try:
        with engine.begin() as connection:
            existing = connection.execute(
                text("SELECT to_regclass(:target)"),
                {"target": SPATIAL_TABLE},
            ).scalar_one()
            if existing is not None:
                comment = connection.execute(
                    text(
                        "SELECT obj_description(to_regclass(:target), 'pg_class')"
                    ),
                    {"target": SPATIAL_TABLE},
                ).scalar_one()
                if comment != OWNERSHIP_COMMENT:
                    raise RuntimeError(
                        f"{SPATIAL_TABLE} already exists and is not marked as "
                        "pipeline-managed. It was not changed."
                    )
                if not refresh_owned_table:
                    LOGGER.info(
                        "%s already exists; skipping table refresh.",
                        SPATIAL_TABLE,
                    )
                    return

            spatial.to_postgis(
                name=staging_table,
                con=connection,
                schema="public",
                if_exists="fail",
                index=False,
                chunksize=500,
            )
            geometry_index = connection.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = :table
                      AND indexdef ILIKE '%USING gist (geom)%'
                    LIMIT 1
                    """
                ),
                {"table": staging_table},
            ).scalar_one_or_none()
            if geometry_index is None:
                raise RuntimeError(
                    f"GeoPandas did not create a GiST index on {staging_table}."
                )
            connection.execute(
                text(
                    f'ALTER TABLE public."{staging_table}" '
                    f'ADD CONSTRAINT "uq_{staging_table}_boundary_fid" '
                    "UNIQUE (boundary_fid)"
                )
            )
            state_index = f"idx_{staging_table}_state_district"
            unique_constraint = f"uq_{staging_table}_boundary_fid"
            connection.execute(
                text(
                    f'CREATE INDEX "{state_index}" '
                    f'ON public."{staging_table}" (state, district)'
                )
            )
            if existing is not None:
                connection.execute(
                    text("DROP TABLE public.rice_district_spatial")
                )
            connection.execute(
                text(
                    f'ALTER TABLE public."{staging_table}" '
                    "RENAME TO rice_district_spatial"
                )
            )
            connection.execute(
                text(
                    f'ALTER INDEX public."{geometry_index}" '
                    "RENAME TO idx_rice_district_spatial_geom"
                )
            )
            connection.execute(
                text(
                    f'ALTER INDEX public."{state_index}" '
                    "RENAME TO idx_rice_district_spatial_state_district"
                )
            )
            connection.execute(
                text(
                    'ALTER TABLE public.rice_district_spatial '
                    f'RENAME CONSTRAINT "{unique_constraint}" '
                    "TO uq_rice_district_spatial_boundary_fid"
                )
            )
            connection.execute(
                text(
                    f'COMMENT ON TABLE public.rice_district_spatial '
                    f"IS '{OWNERSHIP_COMMENT}'"
                )
            )
            row_count = connection.execute(
                text("SELECT COUNT(*) FROM public.rice_district_spatial")
            ).scalar_one()
            if row_count != len(spatial):
                raise RuntimeError(
                    f"PostGIS output count mismatch: {row_count} vs {len(spatial)}."
                )
            invalid_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.rice_district_spatial
                    WHERE geom IS NULL OR ST_IsEmpty(geom)
                       OR NOT ST_IsValid(geom) OR ST_SRID(geom) <> 4326
                    """
                )
            ).scalar_one()
            if invalid_count:
                raise RuntimeError(
                    f"PostGIS spatial output has {invalid_count} invalid features."
                )
    finally:
        engine.dispose()


def integrate_spatial_data(
    district_summary: pd.DataFrame | None = None,
) -> dict[str, object]:
    ensure_output_directories()
    if district_summary is None:
        path = CSV_OUTPUT / "district_rice_summary.csv"
        if not path.is_file():
            raise FileNotFoundError(
                f"District summary is missing: {path}. Run Stage 2 first."
            )
        district_summary = pd.read_csv(path)
    required = {
        "state",
        "district",
        "state_key",
        "district_key",
        "total_area",
        "total_production",
        "crop_yield",
    }
    missing = required.difference(district_summary.columns)
    if missing:
        raise ValueError(
            "District summary is missing required columns: "
            + ", ".join(sorted(missing))
        )

    boundaries, legacy = _read_spatial_data()
    assignments, assignment_issues = _derive_spatial_states(boundaries, legacy)
    boundary_frame = boundaries.merge(
        assignments, on="boundary_fid", validate="one_to_one"
    )
    boundary_frame["boundary_district_key"] = boundary_frame["shapeName"].map(
        normalize_name
    )
    boundary_frame["boundary_state_key"] = boundary_frame["derived_state"].map(
        normalize_state
    )
    verified_crosswalk = _load_verified_crosswalk(
        district_summary, boundary_frame
    )
    spatial, unmatched, matches, match_audit = _match_summaries(
        boundaries, assignments, district_summary, verified_crosswalk
    )
    _validate_spatial_result(spatial)

    unmatched.to_csv(CSV_OUTPUT / "unmatched_rice_districts.csv", index=False)
    match_audit.to_csv(CSV_OUTPUT / "district_match_audit.csv", index=False)
    verified_crosswalk[CROSSWALK_COLUMNS].to_csv(
        CSV_OUTPUT / "verified_district_crosswalk.csv", index=False
    )
    assignment_issues.to_csv(
        CSV_OUTPUT / "spatial_state_assignment_issues.csv", index=False
    )
    status_counts = match_audit["match_status"].value_counts()
    match_report = pd.DataFrame(
        [
            ("boundary_features", len(boundaries)),
            ("agriculture_district_summaries", len(district_summary)),
            ("exact_matches", int(status_counts.get("matched_exact", 0))),
            (
                "verified_crosswalk_matches",
                int(status_counts.get("matched_verified_crosswalk", 0)),
            ),
            ("matched_district_summaries", len(matches)),
            ("unmatched_district_summaries", len(unmatched)),
            (
                "ambiguous_district_matches",
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
            ("boundary_state_assignment_issues", len(assignment_issues)),
            ("boundary_features_with_rice_data", int(spatial["crop_yield"].notna().sum())),
            ("boundary_features_without_rice_data", int(spatial["crop_yield"].isna().sum())),
            (
                "duplicate_agriculture_to_boundary_matches",
                int(
                    unmatched["match_status"]
                    .eq("multiple_summaries_to_one_boundary")
                    .sum()
                ),
            ),
        ],
        columns=["metric", "value"],
    )
    match_report.to_csv(CSV_OUTPUT / "spatial_match_summary.csv", index=False)

    _persist_spatial_table(spatial)
    LOGGER.info(
        "Spatial integration complete: %d/%d agriculture summaries matched, "
        "%d unmatched, including %d state conflicts requiring review; "
        "%d verified crosswalk matches and %d state-assignment issues.",
        len(matches),
        len(district_summary),
        len(unmatched),
        int(
            unmatched["match_status"]
            .eq("state_mismatch_requires_review")
            .sum()
        ),
        int(status_counts.get("matched_verified_crosswalk", 0)),
        len(assignment_issues),
    )
    return {
        "spatial": spatial,
        "unmatched": unmatched,
        "matches": matches,
        "match_audit": match_audit,
        "verified_crosswalk": verified_crosswalk,
        "assignment_issues": assignment_issues,
        "match_report": match_report,
        "duplicate_match_rows": int(
            unmatched["match_status"]
            .eq("multiple_summaries_to_one_boundary")
            .sum()
        ),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    integrate_spatial_data()
