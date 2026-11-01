"""Clean Rice observations and export district and state summaries."""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.pipeline_utils import (
    AREA_UNITS,
    CSV_OUTPUT,
    PRODUCTION_UNITS,
    create_database_engine,
    ensure_output_directories,
    normalize_name,
    normalize_state,
)


LOGGER = logging.getLogger("agri_gis.stage2")
SOURCE_COLUMNS = [
    "state",
    "district",
    "crop",
    "year",
    "season",
    "area",
    "production",
    "yield",
]


def parse_year(value: object) -> tuple[object, bool]:
    if pd.isna(value):
        return pd.NA, False
    match = re.fullmatch(
        r"\s*(\d{4})(?:\s*-\s*(?:\d{2}|\d{4}))?\s*",
        str(value),
    )
    if match is None:
        return pd.NA, False
    return int(match.group(1)), True


def prepare_rice_observations(
    raw: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, int],
]:
    raw = raw.copy()
    raw["crop_clean"] = raw["crop"].astype("string").str.strip()
    rice_raw = raw[
        raw["crop_clean"].str.casefold().eq("rice").fillna(False)
    ].copy()
    if rice_raw.empty:
        raise ValueError("No Rice records were found in public.agriculture.")

    rice_unique = rice_raw.drop_duplicates(subset=SOURCE_COLUMNS).copy()
    rice_unique["state"] = (
        rice_unique["state"].astype("string").str.strip().str.title()
    )
    rice_unique["district"] = (
        rice_unique["district"].astype("string").str.strip().str.title()
    )
    rice_unique["crop"] = rice_unique["crop_clean"]
    rice_unique["year_raw"] = rice_unique["year"]
    parsed_years = rice_unique["year"].map(parse_year)
    rice_unique["year_start"] = pd.array(
        [year for year, _ in parsed_years],
        dtype="Int64",
    )
    valid_year = pd.Series(
        [valid for _, valid in parsed_years],
        index=rice_unique.index,
    )
    year_text = rice_unique["year"].astype("string").str.strip()
    missing_year = rice_unique["year"].isna() | year_text.eq("").fillna(False)
    all_year_results = raw["year"].map(parse_year)
    all_year_text = raw["year"].astype("string").str.strip()
    all_crop_missing_year_count = int(
        raw["year"].isna().sum() + all_year_text.eq("").fillna(False).sum()
    )
    all_crop_invalid_year_count = sum(
        not is_valid
        and not pd.isna(raw_year)
        and str(raw_year).strip() != ""
        for raw_year, (_, is_valid) in zip(raw["year"], all_year_results)
    )

    rice_unique["area"] = pd.to_numeric(
        rice_unique["area"], errors="coerce"
    )
    rice_unique["production"] = pd.to_numeric(
        rice_unique["production"], errors="coerce"
    )
    rice_unique["state_key"] = rice_unique["state"].map(normalize_state)
    rice_unique["district_key"] = rice_unique["district"].map(normalize_name)

    missing_area = rice_unique["area"].isna()
    missing_production = rice_unique["production"].isna()
    invalid_numeric = (
        ~np.isfinite(rice_unique["area"].fillna(0))
        | ~np.isfinite(rice_unique["production"].fillna(0))
        | rice_unique["area"].le(0)
        | rice_unique["production"].lt(0)
    )
    missing_names = (
        rice_unique["state_key"].eq("")
        | rice_unique["district_key"].eq("")
    )
    rice_clean = rice_unique.loc[~missing_names].copy()
    valid = rice_unique.loc[
        valid_year
        & ~missing_year
        & ~missing_area
        & ~missing_production
        & ~invalid_numeric
        & ~missing_names
    ].copy()
    invalid_year_count = int((~valid_year & ~missing_year).sum())
    counts = {
        "rice_missing_year_count": int(missing_year.sum()),
        "rice_invalid_year_count": invalid_year_count,
        "missing_area_count": int(missing_area.sum()),
        "missing_production_count": int(missing_production.sum()),
        "invalid_numeric_count": int(invalid_numeric.sum()),
        "missing_state_count": int(rice_unique["state_key"].eq("").sum()),
        "missing_district_count": int(
            rice_unique["district_key"].eq("").sum()
        ),
        "all_crop_invalid_year_count": int(all_crop_invalid_year_count),
        "all_crop_missing_year_count": all_crop_missing_year_count,
    }
    return rice_raw, rice_unique, rice_clean, valid, {
        **counts,
        "rice_rows_after_name_cleaning": int(len(rice_clean)),
    }


def aggregate_rice_records(
    valid: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    district_summary = (
        valid.groupby(
            ["state", "district", "state_key", "district_key"],
            as_index=False,
            dropna=False,
        )
        .agg(
            total_area=("area", "sum"),
            total_production=("production", "sum"),
            observation_count=("production", "size"),
            first_year=("year_start", "min"),
            last_year=("year_start", "max"),
        )
    )
    district_summary["crop_yield"] = np.divide(
        district_summary["total_production"],
        district_summary["total_area"],
        out=np.full(len(district_summary), np.nan, dtype=float),
        where=district_summary["total_area"].to_numpy() > 0,
    )
    district_summary["yield_units"] = (
        "source production unit / source area unit (unverified)"
    )
    district_summary["area_units"] = AREA_UNITS
    district_summary["production_units"] = PRODUCTION_UNITS

    state_summary = (
        valid.groupby(["state", "state_key"], as_index=False, dropna=False)
        .agg(
            total_area=("area", "sum"),
            total_production=("production", "sum"),
            observation_count=("production", "size"),
            district_count=("district_key", "nunique"),
            first_year=("year_start", "min"),
            last_year=("year_start", "max"),
        )
    )
    state_summary["average_yield"] = np.divide(
        state_summary["total_production"],
        state_summary["total_area"],
        out=np.full(len(state_summary), np.nan, dtype=float),
        where=state_summary["total_area"].to_numpy() > 0,
    )
    state_summary["yield_units"] = (
        "source production unit / source area unit (unverified)"
    )
    state_summary["area_units"] = AREA_UNITS
    state_summary["production_units"] = PRODUCTION_UNITS
    return district_summary, state_summary


def build_data_dictionary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("state", "Source state label", "Not applicable", "As supplied"),
            ("district", "Source district label", "Not applicable", "As supplied"),
            ("crop", "Crop name", "Not applicable", "As supplied"),
            ("year", "Source year / agricultural year label", "Year label", "Validated format; source retained"),
            ("season", "Agricultural season", "Not applicable", "As supplied"),
            ("area", "Agricultural area", AREA_UNITS, "Unit unverified; see config/agriculture_source_metadata.csv"),
            ("production", "Agricultural production", PRODUCTION_UNITS, "Unit unverified; see config/agriculture_source_metadata.csv"),
            ("yield", "Source-reported row-level yield", "Unverified", "Retained in the source; not averaged for district yield"),
            ("crop_yield", "Aggregated production divided by aggregated area", "Production unit / area unit (unverified)", "Calculated after valid-row aggregation"),
            ("boundary_area_km2", "District polygon area in EPSG:6933", "km2", "Calculated from boundary geometry; not agricultural area"),
        ],
        columns=["column", "definition", "unit", "status_or_method"],
    )


def load_agriculture_data() -> pd.DataFrame:
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            return pd.read_sql_query(
                text(
                    """
                    SELECT state, district, crop, year, season,
                           area, production, "yield"
                    FROM public.agriculture
                    """
                ),
                connection,
            )
    finally:
        engine.dispose()


def build_data_quality_summary(
    raw: pd.DataFrame,
    rice_raw: pd.DataFrame,
    rice_unique: pd.DataFrame,
    rice_clean: pd.DataFrame,
    valid: pd.DataFrame,
    invalid_year_count: int,
    missing_year_count: int,
    missing_area_count: int,
    missing_production_count: int,
    invalid_numeric_count: int,
    missing_state_count: int,
    missing_district_count: int,
    all_crop_invalid_year_count: int,
    all_crop_missing_year_count: int,
) -> pd.DataFrame:
    entries = [
        ("database_rows_all_crops", len(raw), "Read-only source row count."),
        (
            "exact_duplicate_rows_all_crops",
            len(raw) - len(raw.drop_duplicates()),
            "Exact duplicate source rows; source table is not modified.",
        ),
        ("rice_rows_raw", len(rice_raw), "Rows before exact deduplication."),
        (
            "rice_missing_area_rows_raw",
            int(pd.to_numeric(rice_raw["area"], errors="coerce").isna().sum()),
            "Raw Rice rows, including exact duplicate copies.",
        ),
        (
            "rice_missing_production_rows_raw",
            int(
                pd.to_numeric(
                    rice_raw["production"], errors="coerce"
                ).isna().sum()
            ),
            "Raw Rice rows, including exact duplicate copies.",
        ),
        (
            "rice_exact_duplicate_rows",
            len(rice_raw) - len(rice_unique),
            "Exact duplicate Rice rows excluded from calculations.",
        ),
        ("rice_distinct_source_rows", len(rice_unique), "After exact deduplication."),
        (
            "rice_invalid_year_rows",
            invalid_year_count,
            "Non-missing year labels not matching YYYY, YYYY-YY, or YYYY-YYYY.",
        ),
        (
            "rice_missing_year_rows",
            missing_year_count,
            "NULL or blank Rice year values; excluded from calculations.",
        ),
        (
            "all_crop_invalid_year_rows",
            all_crop_invalid_year_count,
            "Invalid non-null year labels across all crops.",
        ),
        (
            "all_crop_missing_year_rows",
            all_crop_missing_year_count,
            "NULL or blank year values across all crops.",
        ),
        (
            "rice_missing_area_rows",
            missing_area_count,
            "Missing or non-numeric area; never treated as zero.",
        ),
        (
            "rice_missing_production_rows",
            missing_production_count,
            "Missing or non-numeric production; never treated as zero.",
        ),
        (
            "rice_missing_state_rows",
            missing_state_count,
            "Missing/blank state after exact deduplication.",
        ),
        (
            "rice_missing_district_rows",
            missing_district_count,
            "Missing/blank district after exact deduplication.",
        ),
        (
            "rice_invalid_numeric_rows",
            invalid_numeric_count,
            "Non-positive area or negative/non-finite area/production values.",
        ),
        (
            "rice_valid_analytical_rows",
            len(valid),
            "Rows included in district/state aggregation.",
        ),
        (
            "rice_rows_excluded_from_analysis",
            len(rice_unique) - len(valid),
            "Unique Rice rows excluded for year, missingness, or invalid values.",
        ),
        (
            "rice_rows_after_name_cleaning",
            len(rice_clean),
            "Unique Rice rows with non-empty normalized state and district names.",
        ),
        (
            "district_summary_records",
            -1,
            "Filled after district summary is calculated.",
        ),
        (
            "state_summary_records",
            -1,
            "Filled after state summary is calculated.",
        ),
        (
            "area_unit",
            AREA_UNITS,
            "Source unit has not been verified; values are not relabeled.",
        ),
        (
            "production_unit",
            PRODUCTION_UNITS,
            "Source unit has not been verified; values are not relabeled.",
        ),
        (
            "rice_yield_definition",
            "total production / total area",
            "Yield units remain unverified until source documentation is available.",
        ),
    ]
    return pd.DataFrame(entries, columns=["metric", "value", "details"])


def process_agriculture_data() -> dict[str, pd.DataFrame]:
    ensure_output_directories()
    raw = load_agriculture_data()
    missing_columns = set(SOURCE_COLUMNS).difference(raw.columns)
    if missing_columns:
        raise ValueError(
            "Agriculture table is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    rice_raw, rice_unique, rice_clean, valid, quality_counts = (
        prepare_rice_observations(raw)
    )
    LOGGER.info(
        "Rice source rows: %d; exact duplicate rows excluded: %d; "
        "distinct Rice observations: %d",
        len(rice_raw),
        len(rice_raw) - len(rice_unique),
        len(rice_unique),
    )
    LOGGER.info(
        "Rice quality checks: invalid year=%d, missing year=%d, missing area=%d, "
        "missing production=%d, invalid numeric=%d, valid rows=%d",
        quality_counts["rice_invalid_year_count"],
        quality_counts["rice_missing_year_count"],
        quality_counts["missing_area_count"],
        quality_counts["missing_production_count"],
        quality_counts["invalid_numeric_count"],
        len(valid),
    )
    if quality_counts["rice_invalid_year_count"]:
        LOGGER.warning(
            "%d distinct Rice rows have invalid year labels and were excluded.",
            quality_counts["rice_invalid_year_count"],
        )
    if (
        quality_counts["rice_missing_year_count"]
        or quality_counts["missing_area_count"]
        or quality_counts["missing_production_count"]
        or quality_counts["invalid_numeric_count"]
    ):
        LOGGER.warning(
            "Rice rows with missing or invalid values were excluded from "
            "calculations; source records were not modified."
        )

    if valid.empty:
        raise ValueError(
            "No Rice rows remain after year, missing-value, and numeric validation."
        )

    district_summary, state_summary = aggregate_rice_records(valid)

    quality = build_data_quality_summary(
        raw=raw,
        rice_raw=rice_raw,
        rice_unique=rice_unique,
        rice_clean=rice_clean,
        valid=valid,
        invalid_year_count=quality_counts["rice_invalid_year_count"],
        missing_year_count=quality_counts["rice_missing_year_count"],
        missing_area_count=quality_counts["missing_area_count"],
        missing_production_count=quality_counts["missing_production_count"],
        invalid_numeric_count=quality_counts["invalid_numeric_count"],
        missing_state_count=quality_counts["missing_state_count"],
        missing_district_count=quality_counts["missing_district_count"],
        all_crop_invalid_year_count=quality_counts[
            "all_crop_invalid_year_count"
        ],
        all_crop_missing_year_count=quality_counts[
            "all_crop_missing_year_count"
        ],
    )
    quality.loc[
        quality["metric"].eq("district_summary_records"), "value"
    ] = len(district_summary)
    quality.loc[quality["metric"].eq("state_summary_records"), "value"] = len(
        state_summary
    )

    district_path = CSV_OUTPUT / "district_rice_summary.csv"
    state_path = CSV_OUTPUT / "state_rice_summary.csv"
    quality_path = CSV_OUTPUT / "rice_data_quality_summary.csv"
    district_summary.to_csv(district_path, index=False)
    state_summary.to_csv(state_path, index=False)
    quality.to_csv(quality_path, index=False)
    build_data_dictionary().to_csv(
        CSV_OUTPUT / "agriculture_data_dictionary.csv",
        index=False,
    )
    LOGGER.info(
        "Saved %d district summaries, %d state summaries, and data-quality "
        "results under %s.",
        len(district_summary),
        len(state_summary),
        CSV_OUTPUT,
    )
    return {
        "district_summary": district_summary,
        "state_summary": state_summary,
        "data_quality": quality,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    process_agriculture_data()
