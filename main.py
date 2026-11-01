"""Run the complete agricultural GIS workflow without rerunning Stage 1."""

from __future__ import annotations

import logging
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import text

from src.generate_charts import generate_charts
from src.generate_qgis_map import generate_qgis_map
from src.generate_report import generate_report
from src.pipeline_utils import (
    BOUNDARY_TABLE,
    CHART_OUTPUT,
    CSV_OUTPUT,
    MAP_OUTPUT,
    PROJECT_ROOT,
    REPORT_OUTPUT,
    SPATIAL_TABLE,
    configure_logging,
    create_database_engine,
    ensure_output_directories,
)
from src.process_agriculture_data import process_agriculture_data
from src.spatial_analysis import run_spatial_analysis
from src.spatial_integration import integrate_spatial_data


LOGGER = logging.getLogger("agri_gis.main")
AGRICULTURE_COLUMNS = {
    "state": "text",
    "district": "text",
    "crop": "text",
    "year": "text",
    "season": "text",
    "area": "double precision",
    "production": "double precision",
    "yield": "double precision",
}
CHART_FILES = (
    "top_10_rice_production.png",
    "top_10_rice_yield.png",
    "state_average_yield.png",
    "state_production.png",
    "area_vs_production.png",
    "district_rice_yield_distribution.png",
)


def validate_project_configuration() -> None:
    required_files = (
        PROJECT_ROOT / "Data" / "agridata.csv",
        PROJECT_ROOT
        / "Dissolve_Clip_Project"
        / "output"
        / "districts_with_state.gpkg",
        PROJECT_ROOT / "config" / "verified_district_crosswalk.csv",
        PROJECT_ROOT / "config" / "agriculture_source_metadata.csv",
    )
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Required project inputs are missing: " + ", ".join(missing)
        )
    crosswalk_header = {
        "original_agriculture_state",
        "original_agriculture_district",
        "verified_boundary_state",
        "verified_boundary_district",
        "matching_method",
        "evidence_source",
        "verification_status",
        "reviewer_notes",
    }
    crosswalk_columns = set(
        pd.read_csv(
            PROJECT_ROOT / "config" / "verified_district_crosswalk.csv",
            nrows=0,
        ).columns
    )
    if not crosswalk_header.issubset(crosswalk_columns):
        raise ValueError(
            "District crosswalk template is missing required columns: "
            + ", ".join(sorted(crosswalk_header - crosswalk_columns))
        )
    LOGGER.info(
        "Project configuration verified; source measurement units remain "
        "unverified until documentary evidence is supplied."
    )


def verify_database_and_stage1() -> None:
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            database, postgis_version = connection.execute(
                text(
                    """
                    SELECT current_database(),
                           (SELECT extversion
                            FROM pg_extension
                            WHERE extname = 'postgis')
                    """
                )
            ).one()
            if not postgis_version:
                raise RuntimeError(
                    "PostGIS is not installed in the configured database."
                )
            agriculture_columns = {
                column: data_type
                for column, data_type in connection.execute(
                    text(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'agriculture'
                        """
                    )
                ).all()
            }
            if not agriculture_columns:
                raise RuntimeError("public.agriculture does not exist.")
            missing_agriculture_columns = set(AGRICULTURE_COLUMNS) - set(
                agriculture_columns
            )
            if missing_agriculture_columns:
                raise RuntimeError(
                    "public.agriculture is missing columns: "
                    + ", ".join(sorted(missing_agriculture_columns))
                )
            invalid_types = {
                column: (agriculture_columns[column], expected_type)
                for column, expected_type in AGRICULTURE_COLUMNS.items()
                if agriculture_columns[column] != expected_type
            }
            if invalid_types:
                raise RuntimeError(
                    "public.agriculture has unexpected column types "
                    f"(actual, expected): {invalid_types}."
                )
            agriculture_count = connection.execute(
                text("SELECT COUNT(*) FROM public.agriculture")
            ).scalar_one()
            if agriculture_count <= 0:
                raise RuntimeError("public.agriculture contains no records.")
            boundary_result = connection.execute(
                text(
                    """
                    SELECT COUNT(*) AS feature_count,
                           COUNT(*) FILTER (
                               WHERE geom IS NULL OR ST_IsEmpty(geom)
                                  OR NOT ST_IsValid(geom)
                           ) AS invalid_geometries,
                           COUNT(DISTINCT ST_SRID(geom)) AS srid_count,
                           MIN(ST_SRID(geom)) AS srid,
                           COUNT(DISTINCT (
                               upper(btrim("state_name")),
                               upper(btrim("shapeName"))
                           )) AS district_keys
                    FROM public.district_boundaries
                    """
                )
            ).one()
            count, invalid, srid_count, srid, district_keys = boundary_result
            if count != 735:
                raise RuntimeError(
                    f"{BOUNDARY_TABLE} must contain 735 features; found {count}."
                )
            if invalid:
                raise RuntimeError(
                    f"{BOUNDARY_TABLE} contains {invalid} invalid geometries."
                )
            if srid_count != 1 or srid != 4326:
                raise RuntimeError(
                    f"{BOUNDARY_TABLE} must use SRID 4326; found {srid}."
                )
            if district_keys != count:
                raise RuntimeError(
                    f"{BOUNDARY_TABLE} has {district_keys} unique district keys "
                    "for 735 features."
                )
            has_gist_index = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                          AND tablename = 'district_boundaries'
                          AND indexdef ILIKE '%USING gist (geom)%'
                    )
                    """
                )
            ).scalar_one()
            if not has_gist_index:
                raise RuntimeError(
                    "Stage 1 GiST index on district_boundaries.geom is missing."
                )
            legacy_count = connection.execute(
                text("SELECT COUNT(*) FROM public.indian_districts")
            ).scalar_one()
            if legacy_count != 693:
                raise RuntimeError(
                    "State overlay reference public.indian_districts must "
                    f"contain 693 features; found {legacy_count}."
                )
            LOGGER.info(
                "Database %s, PostGIS %s; agriculture rows=%d; Stage 1 "
                "verified: %d features, SRID %d, GiST index present; "
                "legacy overlay reference=%d features.",
                database,
                postgis_version,
                agriculture_count,
                count,
                srid,
                legacy_count,
            )
    finally:
        engine.dispose()


def validate_final_outputs() -> None:
    required_csv = (
        "district_rice_summary.csv",
        "state_rice_summary.csv",
        "rice_data_quality_summary.csv",
        "unmatched_rice_districts.csv",
        "verified_district_crosswalk.csv",
        "spatial_match_summary.csv",
        "district_match_audit.csv",
        "agriculture_data_dictionary.csv",
    )
    for filename in required_csv:
        path = CSV_OUTPUT / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Required CSV output is missing or empty: {path}")
    district_summary = pd.read_csv(CSV_OUTPUT / "district_rice_summary.csv")
    match_audit = pd.read_csv(CSV_OUTPUT / "district_match_audit.csv")
    unmatched = pd.read_csv(CSV_OUTPUT / "unmatched_rice_districts.csv")
    match_summary = pd.read_csv(CSV_OUTPUT / "spatial_match_summary.csv")
    if district_summary.empty or len(match_audit) != len(district_summary):
        raise RuntimeError(
            "District match audit must have one row for each agriculture "
            "district summary."
        )
    match_metrics = dict(
        zip(match_summary["metric"], pd.to_numeric(match_summary["value"]))
    )
    audit_status_counts = match_audit["match_status"].value_counts()
    exact_count = int(audit_status_counts.get("matched_exact", 0))
    crosswalk_count = int(
        audit_status_counts.get("matched_verified_crosswalk", 0)
    )
    unmatched_count = len(unmatched)
    if (
        exact_count + crosswalk_count + unmatched_count
        != len(district_summary)
    ):
        raise RuntimeError(
            "Exact, verified-crosswalk, and unresolved match counts do not "
            "sum to the district summary count."
        )
    for metric, actual in (
        ("exact_matches", exact_count),
        ("verified_crosswalk_matches", crosswalk_count),
        ("unmatched_district_summaries", unmatched_count),
    ):
        if int(match_metrics.get(metric, -1)) != actual:
            raise RuntimeError(
                f"Match summary metric {metric!r} does not match the audit."
            )
    for filename in CHART_FILES:
        path = CHART_OUTPUT / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Required chart is missing or empty: {path}")
        with Image.open(path) as image:
            dpi = image.info.get("dpi", (0, 0))
            if image.format != "PNG" or min(dpi) < 299:
                raise RuntimeError(
                    f"Chart {path.name} must be a PNG at 300 DPI; found {dpi}."
                )

    map_image = MAP_OUTPUT / "India_Rice_Yield_Map.png"
    map_pdf = MAP_OUTPUT / "India_Rice_Yield_Map.pdf"
    qgis_project = MAP_OUTPUT / "India_Rice_Yield_Project.qgz"
    map_data = MAP_OUTPUT / "India_Rice_Yield_Data.gpkg"
    report_file = REPORT_OUTPUT / "Agriculture_GIS_Analysis_Report.pdf"
    for path in (map_image, map_pdf, qgis_project, map_data, report_file):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Required final output is missing or empty: {path}")

    with Image.open(map_image) as image:
        if image.format != "PNG" or min(image.size) < 1000:
            raise RuntimeError(
                f"Map PNG failed format/resolution validation: {image.size}."
            )
    map_pdf_reader = PdfReader(str(map_pdf), strict=True)
    report_reader = PdfReader(str(report_file), strict=True)
    if len(map_pdf_reader.pages) != 1 or not report_reader.pages:
        raise RuntimeError("Map or analytical PDF has an unexpected page count.")
    if not any((page.extract_text() or "").strip() for page in report_reader.pages):
        raise RuntimeError("Analytical report PDF contains no extractable text.")

    with zipfile.ZipFile(qgis_project) as archive:
        project_members = [
            member for member in archive.namelist() if member.endswith(".qgs")
        ]
        if not project_members:
            raise RuntimeError("QGIS project archive contains no .qgs project.")
        project_xml = ET.fromstring(archive.read(project_members[0]))
        yield_renderers = [
            renderer
            for renderer in project_xml.iter("renderer-v2")
            if renderer.get("attr") == "crop_yield"
        ]
        if not yield_renderers:
            raise RuntimeError(
                "QGIS project lacks the crop_yield field or Jenks renderer."
            )
        renderer = yield_renderers[0]
        class_count = len(renderer.findall("./ranges/range"))
        renderer_text = ET.tostring(renderer, encoding="unicode")
        if class_count != 5 or "Jenks" not in renderer_text:
            raise RuntimeError(
                "QGIS project must use five Natural Breaks (Jenks) classes; "
                f"found {class_count} ranges."
            )

    with sqlite3.connect(map_data) as connection:
        layer = connection.execute(
            """
            SELECT table_name
            FROM gpkg_contents
            WHERE data_type = 'features'
            """
        ).fetchone()
        if layer is None:
            raise RuntimeError("Map GeoPackage contains no feature layer.")
        feature_count = connection.execute(
            f'SELECT COUNT(*) FROM "{layer[0]}"'
        ).fetchone()[0]
        if feature_count != 735:
            raise RuntimeError(
                f"Map GeoPackage must retain 735 features; found {feature_count}."
            )
        map_yield_count = connection.execute(
            f'SELECT COUNT(*) FROM "{layer[0]}" WHERE crop_yield IS NOT NULL'
        ).fetchone()[0]
        map_unmatched_with_values = connection.execute(
            f"""
            SELECT COUNT(*) FROM "{layer[0]}"
            WHERE match_status = 'no_matching_agriculture_summary'
              AND (total_area IS NOT NULL OR total_production IS NOT NULL
                   OR crop_yield IS NOT NULL)
            """
        ).fetchone()[0]

    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            (
                spatial_count,
                yield_count,
                invalid_count,
                yield_mismatch_count,
                unmatched_with_values,
            ) = connection.execute(
                text(
                    """
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE crop_yield IS NOT NULL),
                           COUNT(*) FILTER (
                               WHERE geom IS NULL OR ST_IsEmpty(geom)
                                  OR NOT ST_IsValid(geom)
                                  OR ST_SRID(geom) <> 4326
                           ),
                           COUNT(*) FILTER (
                               WHERE crop_yield IS NOT NULL
                                 AND ABS(
                                     crop_yield
                                     - total_production / NULLIF(total_area, 0)
                                 ) > 1e-10 * GREATEST(ABS(crop_yield), 1)
                           ),
                           COUNT(*) FILTER (
                               WHERE match_status = 'no_matching_agriculture_summary'
                                 AND (
                                     total_area IS NOT NULL
                                     OR total_production IS NOT NULL
                                     OR crop_yield IS NOT NULL
                                 )
                           )
                    FROM public.rice_district_spatial
                    """
                )
            ).one()
            if (
                spatial_count != 735
                or invalid_count
                or yield_mismatch_count
                or unmatched_with_values
                or map_yield_count != yield_count
                or map_unmatched_with_values
            ):
                raise RuntimeError(
                    "Final spatial table validation failed: "
                    f"features={spatial_count}, invalid={invalid_count}, "
                    f"yield mismatches={yield_mismatch_count}, "
                    f"unmatched with values={unmatched_with_values}, "
                    f"map yields={map_yield_count}/{yield_count}, "
                    f"map unmatched with values={map_unmatched_with_values}."
                )
            LOGGER.info(
                "Final output validation passed; spatial rows=%d, "
                "district yields=%d, charts=%d, map PDFs=valid, report pages=%d.",
                spatial_count,
                yield_count,
                len(CHART_FILES),
                len(report_reader.pages),
            )
    finally:
        engine.dispose()


def run_pipeline() -> None:
    configure_logging()
    ensure_output_directories()
    current_stage = "database and Stage 1 verification"
    try:
        current_stage = "Stage 0 - project configuration validation"
        LOGGER.info("%s", current_stage)
        validate_project_configuration()

        current_stage = "database and Stage 1 verification"
        LOGGER.info("%s", current_stage)
        verify_database_and_stage1()

        current_stage = "Stage 2 - agriculture data processing"
        LOGGER.info("%s", current_stage)
        agriculture = process_agriculture_data()

        current_stage = "Stage 3 - PostGIS spatial integration"
        LOGGER.info("%s", current_stage)
        spatial_join = integrate_spatial_data(
            agriculture["district_summary"]
        )

        current_stage = "Stage 4 - Python spatial analysis"
        LOGGER.info("%s", current_stage)
        analysis = run_spatial_analysis(
            spatial=spatial_join["spatial"],
            district_summary=agriculture["district_summary"],
            state_summary=agriculture["state_summary"],
        )

        current_stage = "Stage 5 - summary chart generation"
        LOGGER.info("%s", current_stage)
        chart_files = generate_charts(analysis)

        current_stage = "Stage 6 - QGIS map generation"
        LOGGER.info("%s", current_stage)
        maps = generate_qgis_map(spatial_join["spatial"])

        current_stage = "Stage 7 - final PDF report"
        LOGGER.info("%s", current_stage)
        report = generate_report()

        current_stage = "final output validation"
        LOGGER.info("%s", current_stage)
        validate_final_outputs()

        LOGGER.info("PIPELINE COMPLETE")
        for key, path in maps.items():
            LOGGER.info("Map output (%s): %s", key, path)
        for chart in chart_files:
            LOGGER.info("Chart output: output\\charts\\%s", chart)
        LOGGER.info("Report output: %s", report)
    except Exception as error:
        LOGGER.exception(
            "Pipeline stopped during %s: %s: %s",
            current_stage,
            type(error).__name__,
            error,
        )
        print(
            f"Pipeline stopped during {current_stage}: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    run_pipeline()
