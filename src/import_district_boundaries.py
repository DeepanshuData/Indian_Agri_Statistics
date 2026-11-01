"""Validate and safely import the district GeoPackage into PostGIS."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import uuid4

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Connection, Engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = (
    PROJECT_ROOT
    / "Dissolve_Clip_Project"
    / "output"
    / "districts_with_state.gpkg"
)
SOURCE_LAYER = "districts_with_state"
TARGET_SCHEMA = "public"
TARGET_TABLE = "district_boundaries"
GEOMETRY_COLUMN = "geom"
DISTRICT_COLUMN = "shapeName"
STATE_COLUMN = "state_name"
LOGGER = logging.getLogger("agri_gis.stage1")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def create_database_engine() -> Engine:
    load_dotenv(PROJECT_ROOT / ".env")
    required = ("DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Missing required database settings in .env: {', '.join(missing)}"
        )

    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "agriculture_db"),
    )
    return create_engine(url, pool_pre_ping=True)


def load_and_validate_source() -> gpd.GeoDataFrame:
    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"District GeoPackage not found: {SOURCE_FILE}")

    layers = gpd.list_layers(SOURCE_FILE)["name"].tolist()
    if SOURCE_LAYER not in layers:
        raise ValueError(
            f"Layer {SOURCE_LAYER!r} is missing from {SOURCE_FILE.name}; "
            f"available layers: {layers}"
        )

    boundaries = gpd.read_file(SOURCE_FILE, layer=SOURCE_LAYER)
    if boundaries.empty:
        raise ValueError("The district boundary layer contains no features.")
    if boundaries.crs is None or boundaries.crs.to_epsg() != 4326:
        raise ValueError(
            f"Expected source CRS EPSG:4326, found {boundaries.crs!s}."
        )

    missing_columns = {
        DISTRICT_COLUMN,
        STATE_COLUMN,
    }.difference(boundaries.columns)
    if missing_columns:
        raise ValueError(
            "Required district fields are missing: "
            + ", ".join(sorted(missing_columns))
        )

    missing_districts = (
        boundaries[DISTRICT_COLUMN].isna()
        | boundaries[DISTRICT_COLUMN].astype(str).str.strip().eq("")
    )
    missing_states = (
        boundaries[STATE_COLUMN].isna()
        | boundaries[STATE_COLUMN].astype(str).str.strip().eq("")
    )
    empty_geometries = boundaries.geometry.isna() | boundaries.geometry.is_empty
    invalid_geometries = ~boundaries.geometry.is_valid
    non_polygon_geometries = ~boundaries.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    )

    keys = (
        boundaries[STATE_COLUMN]
        .astype(str)
        .str.strip()
        .str.upper()
        + "|"
        + boundaries[DISTRICT_COLUMN]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    duplicate_keys = int(keys.duplicated(keep=False).sum())

    errors = []
    for label, count in (
        ("districts with missing names", int(missing_districts.sum())),
        ("districts with missing state labels", int(missing_states.sum())),
        ("empty or missing geometries", int(empty_geometries.sum())),
        ("invalid geometries", int(invalid_geometries.sum())),
        ("non-polygon geometries", int(non_polygon_geometries.sum())),
        ("duplicate state/district keys", duplicate_keys),
    ):
        LOGGER.info("%s: %d", label, count)
        if count:
            errors.append(f"{label}: {count}")

    if errors:
        raise ValueError("Source validation failed: " + "; ".join(errors))

    if boundaries.geometry.name != GEOMETRY_COLUMN:
        boundaries = boundaries.rename_geometry(GEOMETRY_COLUMN)

    LOGGER.info(
        "Validated %d features, CRS EPSG:4326, geometry types: %s",
        len(boundaries),
        boundaries.geom_type.value_counts().to_dict(),
    )
    LOGGER.warning(
        "Source state labels are preserved as supplied; prior comparison found "
        "state-label mismatches against the legacy district boundaries. "
        "Do not use these labels for analytical joins without correction."
    )
    return boundaries


def validate_postgis(connection: Connection) -> str:
    row = connection.execute(
        text(
            """
            SELECT current_database(), current_user,
                   (SELECT extversion
                    FROM pg_extension
                    WHERE extname = 'postgis')
            """
        )
    ).one()
    database_name, database_user, postgis_version = row
    if postgis_version is None:
        raise RuntimeError(
            "PostGIS is not installed in the configured database. "
            "Install/enable PostGIS before importing boundaries."
        )
    LOGGER.info(
        "Connected to database %s as %s; PostGIS %s",
        database_name,
        database_user,
        postgis_version,
    )
    return postgis_version


def source_marker(source_hash: str, feature_count: int) -> str:
    return (
        f"agri-gis-import:v1;sha256={source_hash};"
        f"layer={SOURCE_LAYER};features={feature_count}"
    )


def validate_imported_table(
    connection: Connection,
    table_name: str,
    expected_count: int,
) -> None:
    stats = connection.execute(
        text(
            f"""
            SELECT COUNT(*) AS feature_count,
                   COUNT(*) FILTER (WHERE {GEOMETRY_COLUMN} IS NULL) AS null_geometries,
                   COUNT(*) FILTER (WHERE ST_IsEmpty({GEOMETRY_COLUMN})) AS empty_geometries,
                   COUNT(*) FILTER (WHERE NOT ST_IsValid({GEOMETRY_COLUMN})) AS invalid_geometries,
                   COUNT(*) FILTER (
                       WHERE "{DISTRICT_COLUMN}" IS NULL
                          OR btrim("{DISTRICT_COLUMN}") = ''
                          OR "{STATE_COLUMN}" IS NULL
                          OR btrim("{STATE_COLUMN}") = ''
                   ) AS missing_district_records,
                   COUNT(DISTINCT (
                       upper(btrim("{STATE_COLUMN}")),
                       upper(btrim("{DISTRICT_COLUMN}"))
                   )) AS unique_district_keys
            FROM "{TARGET_SCHEMA}"."{table_name}"
            """
        )
    ).one()
    count, nulls, empties, invalids, missing, unique_keys = stats
    if count != expected_count:
        raise RuntimeError(
            f"Imported feature count mismatch: expected {expected_count}, got {count}."
        )
    if nulls or empties or invalids or missing or unique_keys != count:
        raise RuntimeError(
            "Imported table validation failed: "
            f"null={nulls}, empty={empties}, invalid={invalids}, "
            f"missing_records={missing}, unique_keys={unique_keys}/{count}."
        )

    geometry_metadata = connection.execute(
        text(
            f"""
            SELECT GeometryType({GEOMETRY_COLUMN}), ST_SRID({GEOMETRY_COLUMN}),
                   COUNT(*)
            FROM "{TARGET_SCHEMA}"."{table_name}"
            GROUP BY 1, 2
            """
        )
    ).all()
    if not geometry_metadata or any(
        srid != 4326 or geom_type not in {"POLYGON", "MULTIPOLYGON"} or n != count
        for geom_type, srid, n in geometry_metadata
    ):
        raise RuntimeError(
            f"Unexpected imported geometry type/SRID: {geometry_metadata}"
        )

    has_spatial_index = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = :schema
                  AND tablename = :table
                  AND indexdef ILIKE '%USING gist (geom)%'
            )
            """
        ),
        {"schema": TARGET_SCHEMA, "table": table_name},
    ).scalar_one()
    if not has_spatial_index:
        raise RuntimeError(
            f"No GiST spatial index was found on {TARGET_SCHEMA}.{table_name}."
        )

    LOGGER.info(
        "Verified %d features; geometry metadata: %s; GiST index: present",
        count,
        geometry_metadata,
    )


def import_boundaries(engine: Engine, boundaries: gpd.GeoDataFrame) -> None:
    source_hash = hashlib.sha256(SOURCE_FILE.read_bytes()).hexdigest()
    marker = source_marker(source_hash, len(boundaries))
    target_identifier = f"{TARGET_SCHEMA}.{TARGET_TABLE}"

    with engine.begin() as connection:
        validate_postgis(connection)
        existing = connection.execute(
            text("SELECT to_regclass(:qualified_name)"),
            {"qualified_name": target_identifier},
        ).scalar_one()

        if existing is not None:
            comment = connection.execute(
                text(
                    "SELECT obj_description(to_regclass(:qualified_name), 'pg_class')"
                ),
                {"qualified_name": target_identifier},
            ).scalar_one()
            if comment != marker:
                raise RuntimeError(
                    f"{target_identifier} already exists and is not marked as "
                    "this exact source import. It was not changed. Rename or "
                    "back up the existing table before choosing another target."
                )
            validate_imported_table(connection, TARGET_TABLE, len(boundaries))
            LOGGER.info(
                "%s already contains this exact source import; skipping write.",
                target_identifier,
            )
            return

        staging_table = f"district_boundaries_load_{uuid4().hex[:10]}"
        boundaries.to_postgis(
            name=staging_table,
            con=connection,
            schema=TARGET_SCHEMA,
            if_exists="fail",
            index=False,
            chunksize=500,
        )
        staging_index = f"idx_{staging_table}_geom"
        validate_imported_table(connection, staging_table, len(boundaries))

        connection.exec_driver_sql(
            f'ALTER TABLE "{TARGET_SCHEMA}"."{staging_table}" '
            f'RENAME TO "{TARGET_TABLE}"'
        )
        connection.exec_driver_sql(
            f'ALTER INDEX "{TARGET_SCHEMA}"."{staging_index}" '
            f'RENAME TO "idx_{TARGET_TABLE}_geom"'
        )
        escaped_marker = marker.replace("'", "''")
        connection.exec_driver_sql(
            f'COMMENT ON TABLE "{TARGET_SCHEMA}"."{TARGET_TABLE}" '
            f"IS '{escaped_marker}'"
        )
        validate_imported_table(connection, TARGET_TABLE, len(boundaries))

    LOGGER.info(
        "Imported %d district features into %s.",
        len(boundaries),
        target_identifier,
    )


def main() -> None:
    configure_logging()
    boundaries = load_and_validate_source()
    engine = create_database_engine()
    try:
        import_boundaries(engine, boundaries)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
