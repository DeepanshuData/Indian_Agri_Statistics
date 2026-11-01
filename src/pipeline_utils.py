"""Shared configuration and data-cleaning helpers for the GIS pipeline."""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "output"
CSV_OUTPUT = OUTPUT_ROOT / "csv"
CHART_OUTPUT = OUTPUT_ROOT / "charts"
MAP_OUTPUT = OUTPUT_ROOT / "maps"
REPORT_OUTPUT = OUTPUT_ROOT / "reports"
LOG_OUTPUT = PROJECT_ROOT / "logs"
AGRICULTURE_TABLE = "public.agriculture"
BOUNDARY_TABLE = "public.district_boundaries"
SPATIAL_TABLE = "public.rice_district_spatial"
AREA_UNITS = "unknown"
PRODUCTION_UNITS = "unknown"


def configure_logging() -> None:
    LOG_OUTPUT.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    file_handler = logging.FileHandler(
        LOG_OUTPUT / "agriculture_gis_pipeline.log", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def create_database_engine() -> Engine:
    load_dotenv(PROJECT_ROOT / ".env")
    required = ("DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "Missing required database settings in .env: "
            + ", ".join(missing)
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


def normalize_name(value: object) -> str:
    if value is None or bool(pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "", ascii_text.upper())

_STATE_ALIASES = {
    normalize_name("ORISSA"): normalize_name("ODISHA"),
    normalize_name("UTTARANCHAL"): normalize_name("UTTARAKHAND"),
    normalize_name("PONDICHERRY"): normalize_name("PUDUCHERRY"),
    normalize_name("A & N ISLANDS"): normalize_name(
        "ANDAMAN & NICOBAR ISLANDS"
    ),
    normalize_name("D & N HAVELI"): normalize_name(
        "DADRA & NAGAR HAVELI AND DAMAN & DIU"
    ),
}


def normalize_state(value: object) -> str:
    normalized = normalize_name(value)
    return _STATE_ALIASES.get(normalized, normalized)


def ensure_output_directories() -> None:
    for folder in (CSV_OUTPUT, CHART_OUTPUT, MAP_OUTPUT, REPORT_OUTPUT):
        folder.mkdir(parents=True, exist_ok=True)
