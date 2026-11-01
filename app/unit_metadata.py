"""Verify whether agriculture units support the dashboard's conversions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METADATA_FILE = PROJECT_ROOT / "config" / "agriculture_source_metadata.csv"
REQUIRED_COLUMNS = {
    "dataset",
    "area_unit",
    "production_unit",
    "yield_unit",
    "evidence_source",
    "verification_status",
}


def agriculture_economics_unit_status(
    metadata_file: Path = METADATA_FILE,
) -> tuple[bool, str]:
    if not metadata_file.is_file():
        return False, f"Source unit metadata is missing: {metadata_file}"

    metadata = pd.read_csv(metadata_file, dtype="string", keep_default_na=False)
    missing_columns = REQUIRED_COLUMNS - set(metadata.columns)
    if missing_columns:
        raise ValueError(
            "Source unit metadata is missing columns: "
            + ", ".join(sorted(missing_columns))
        )
    source_rows = metadata.loc[
        metadata["dataset"].str.strip().str.casefold().eq(
            "agriculture statistics"
        )
    ]
    if len(source_rows) != 1:
        return (
            False,
            "Exactly one Agriculture statistics metadata row is required "
            "before unit-dependent financial estimates can be enabled.",
        )

    source = source_rows.iloc[0]
    if source["verification_status"].strip().casefold() != "verified":
        return (
            False,
            "Automatic production conversion from source yield is disabled "
            "until authoritative area, production, and yield units are "
            "documented and marked verified.",
        )
    if not source["evidence_source"].strip():
        return False, "Verified unit metadata must cite its documentary evidence."

    canonical_units = {
        column: source[column].strip().casefold().replace(" ", "")
        for column in ("area_unit", "production_unit", "yield_unit")
    }
    supported = (
        canonical_units["area_unit"] in {"hectare", "hectares", "ha"}
        and canonical_units["production_unit"]
        in {"tonne", "tonnes", "metrictonne", "metrictonnes", "t"}
        and canonical_units["yield_unit"]
        in {
            "tonne/hectare",
            "tonnes/hectare",
            "tonneperhectare",
            "tonnesperhectare",
            "t/ha",
        }
    )
    if not supported:
        return (
            False,
            "Unit metadata is verified, but the dashboard's financial "
            "conversion currently supports only hectares, tonnes, and "
            "tonnes per hectare.",
        )
    return True, "Source units are verified and supported by dashboard conversions."
