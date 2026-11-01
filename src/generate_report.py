"""Create a PDF report with validation, analysis tables, map, and charts."""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.utils import ImageReader

from src.pipeline_utils import (
    CHART_OUTPUT,
    CSV_OUTPUT,
    MAP_OUTPUT,
    REPORT_OUTPUT,
    ensure_output_directories,
)


LOGGER = logging.getLogger("agri_gis.stage7")
REPORT_FILE = REPORT_OUTPUT / "Agriculture_GIS_Analysis_Report.pdf"
CHART_FILES = [
    "top_10_rice_production.png",
    "top_10_rice_yield.png",
    "state_average_yield.png",
    "state_production.png",
    "area_vs_production.png",
    "district_rice_yield_distribution.png",
]


def _read_csv(filename: str) -> pd.DataFrame:
    path = CSV_OUTPUT / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required report data file is missing: {path}")
    return pd.read_csv(path)


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    safe_text = html.escape(str(value)).replace("\n", "<br/>")
    return Paragraph(safe_text, style)


def _table(
    rows: Iterable[Iterable[object]],
    *,
    widths: list[float] | None = None,
    header: bool = True,
) -> Table:
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    data = []
    for row_index, row in enumerate(rows):
        style = header_style if header and row_index == 0 else cell_style
        data.append([_paragraph(value, style) for value in row])
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d3c8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b5e20")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _fit_image(path: Path, max_width: float, max_height: float) -> Image:
    reader = ImageReader(str(path))
    image_width, image_height = reader.getSize()
    scale = min(max_width / image_width, max_height / image_height)
    return Image(
        str(path),
        width=image_width * scale,
        height=image_height * scale,
    )


def _page_decoration(canvas, document) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor("#d6e2d6"))
    canvas.line(17 * mm, 14 * mm, width - 17 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#526152"))
    canvas.drawString(17 * mm, 9 * mm, "India Agricultural GIS | Rice analysis")
    canvas.drawRightString(
        width - 17 * mm,
        9 * mm,
        f"Page {document.page}",
    )
    canvas.restoreState()


def generate_report() -> Path:
    ensure_output_directories()
    required_outputs = [
        MAP_OUTPUT / "India_Rice_Yield_Map.png",
        MAP_OUTPUT / "India_Rice_Yield_Map.pdf",
        MAP_OUTPUT / "India_Rice_Yield_Project.qgz",
        *(CHART_OUTPUT / name for name in CHART_FILES),
    ]
    missing_outputs = [str(path) for path in required_outputs if not path.is_file()]
    if missing_outputs:
        raise FileNotFoundError(
            "Report cannot be generated because required map/chart outputs "
            "are missing: " + ", ".join(missing_outputs)
        )

    quality = _read_csv("rice_data_quality_summary.csv")
    match_summary = _read_csv("spatial_match_summary.csv")
    top_production = _read_csv("top_10_rice_production.csv")
    top_yield = _read_csv("top_10_rice_yield.csv")
    states = _read_csv("state_rice_analysis.csv")
    unmatched = _read_csv("unmatched_rice_districts.csv")

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=28,
            textColor=colors.HexColor("#174a2a"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1b5e20"),
            spaceBefore=8,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            "ChartTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#174a2a"),
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )

    story = [
        Paragraph("India Agricultural GIS Analysis", styles["ReportTitle"]),
        Paragraph(
            "District-level Rice production and yield | Automated Python, "
            "PostGIS and QGIS workflow",
            styles["ReportBody"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Project overview", styles["SectionHeading"]),
        Paragraph(
            "This report combines the read-only public.agriculture table, "
            "the 735-feature district GeoPackage imported to PostGIS, and a "
            "spatial overlay with the existing 693-feature EPSG:4326 legacy "
            "district reference. Agriculture totals are aggregated over all "
            "valid years and seasons available in the source.",
            styles["ReportBody"],
        ),
        Paragraph("Data sources and validation", styles["SectionHeading"]),
    ]

    selected_metrics = {
        "database_rows_all_crops",
        "exact_duplicate_rows_all_crops",
        "rice_rows_raw",
        "rice_exact_duplicate_rows",
        "rice_distinct_source_rows",
        "rice_invalid_year_rows",
        "rice_missing_year_rows",
        "all_crop_invalid_year_rows",
        "all_crop_missing_year_rows",
        "rice_missing_area_rows",
        "rice_missing_production_rows",
        "rice_valid_analytical_rows",
        "district_summary_records",
        "state_summary_records",
        "area_unit",
        "production_unit",
    }
    quality_view = quality[quality["metric"].isin(selected_metrics)]
    story.append(
        _table(
            [["Validation measure", "Result", "Notes"]]
            + quality_view[["metric", "value", "details"]].values.tolist(),
            widths=[55 * mm, 25 * mm, 95 * mm],
        )
    )
    story.extend(
        [
            Paragraph("Spatial match coverage", styles["SectionHeading"]),
            _table(
                [["Measure", "Count"]]
                + match_summary[["metric", "value"]].values.tolist(),
                widths=[95 * mm, 40 * mm],
            ),
            Paragraph(
                f"The source CSV units for area and production are undocumented. "
                f"Yield values are calculated as total production divided by "
                f"total area, but their units are not assigned. {len(unmatched)} "
                f"agricultural district summaries did not receive a reliable "
                f"boundary match; they remain listed in "
                f"output/csv/unmatched_rice_districts.csv and are excluded from "
                f"the choropleth.",
                styles["ReportBody"],
            ),
            PageBreak(),
            Paragraph("India-wide Rice yield map", styles["SectionHeading"]),
            _fit_image(
                MAP_OUTPUT / "India_Rice_Yield_Map.png",
                175 * mm,
                215 * mm,
            ),
            Paragraph(
                "The map uses five Natural Breaks (Jenks) classes and a green "
                "colour ramp. The project is saved separately as "
                "India_Rice_Yield_Project.qgz; no existing QGIS project was "
                "modified.",
                styles["ReportBody"],
            ),
            PageBreak(),
            Paragraph("District-level findings", styles["SectionHeading"]),
            Paragraph(
                "Top districts are ranked from the full agricultural summary, "
                "including records that could not be spatially matched.",
                styles["ReportBody"],
            ),
            Paragraph("Top 10 Rice production", styles["Heading3"]),
            _table(
                [["District", "State", "Production", "Area", "Yield"]]
                + top_production[
                    [
                        "district",
                        "state",
                        "total_production",
                        "total_area",
                        "crop_yield",
                    ]
                ].values.tolist(),
                widths=[38 * mm, 36 * mm, 34 * mm, 34 * mm, 28 * mm],
            ),
            Spacer(1, 5 * mm),
            Paragraph("Top 10 Rice yield", styles["Heading3"]),
            _table(
                [["District", "State", "Yield", "Production", "Area"]]
                + top_yield[
                    [
                        "district",
                        "state",
                        "crop_yield",
                        "total_production",
                        "total_area",
                    ]
                ].values.tolist(),
                widths=[38 * mm, 36 * mm, 28 * mm, 36 * mm, 32 * mm],
            ),
            PageBreak(),
            Paragraph("State-level Rice production", styles["SectionHeading"]),
            Paragraph(
                "State totals use the source agricultural state labels after "
                "cleaning and alias normalization. They are not silently "
                "reassigned to modern state boundaries.",
                styles["ReportBody"],
            ),
            _table(
                [["State", "Production", "Area", "Average yield"]]
                + states.sort_values(
                    "total_production", ascending=False
                )[
                    ["state", "total_production", "total_area", "average_yield"]
                ].head(20).values.tolist(),
                widths=[52 * mm, 43 * mm, 43 * mm, 38 * mm],
            ),
            PageBreak(),
            Paragraph("Methodology and limitations", styles["SectionHeading"]),
            Paragraph(
                "Exact duplicate source rows are excluded from calculations "
                "without changing the database. Rice rows with invalid years, "
                "missing area or production, negative values, or non-finite "
                "values are excluded and counted in the quality summary. "
                "Area and production are summed by source state and district "
                "before calculating yield; individual row yields are not "
                "averaged.",
                styles["ReportBody"],
            ),
            Paragraph(
                "For spatial matching, normalized state-plus-district names "
                "are tried first. State-conflicting, ambiguous, and "
                "many-to-one matches are not accepted automatically. Only "
                "crosswalk rows marked verified and accompanied by an evidence "
                "reference can override a name mismatch; fuzzy-name candidates "
                "are review hints only. Reference state names are derived by "
                "assigning each GeoPackage district's interior point to the "
                "existing legacy EPSG:4326 districts. Original agriculture "
                "labels remain available in the spatial table and match audit.",
                styles["ReportBody"],
            ),
            Paragraph(
                "District polygon area is measured in EPSG:6933 for spatial "
                "analysis. Agricultural area/production units and the source "
                "boundary vintage are not independently documented. The legacy "
                "693-district reference and 735-feature source have different "
                "coverage and boundary vintages; unmatched records are not "
                "invented, redistributed, or filled with zero.",
                styles["ReportBody"],
            ),
            Paragraph(
                "Unmatched agriculture district examples: "
                + ", ".join(
                    f"{row.state} — {row.district}"
                    for row in unmatched.head(20).itertuples(index=False)
                ),
                styles["ReportBody"],
            ),
        ]
    )

    chart_titles = {
        "top_10_rice_production.png": "Top 10 Rice-Producing Districts",
        "top_10_rice_yield.png": "Top 10 Districts by Rice Yield",
        "state_average_yield.png": "State-wise Average Rice Yield",
        "state_production.png": "State-wise Rice Production",
        "area_vs_production.png": "District Rice Area versus Production",
        "district_rice_yield_distribution.png": "District-wise Rice Yield Distribution",
    }
    for chart_file in CHART_FILES:
        story.extend(
            [
                PageBreak(),
                Paragraph(chart_titles[chart_file], styles["ChartTitle"]),
                _fit_image(
                    CHART_OUTPUT / chart_file,
                    175 * mm,
                    220 * mm,
                ),
                Paragraph(
                    "Source units are unverified; chart axes are deliberately "
                    "not labeled with assumed units.",
                    styles["ReportBody"],
                ),
            ]
        )

    document = SimpleDocTemplate(
        str(REPORT_FILE),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=20 * mm,
        title="India Agricultural GIS Analysis - Rice",
        author="Agricultural GIS Pipeline",
        subject="District and state Rice statistics with PostGIS analysis",
    )
    document.build(
        story,
        onFirstPage=_page_decoration,
        onLaterPages=_page_decoration,
    )
    if not REPORT_FILE.is_file() or REPORT_FILE.stat().st_size == 0:
        raise RuntimeError(f"PDF report was not created: {REPORT_FILE}")
    LOGGER.info("Generated analytical report: %s", REPORT_FILE)
    return REPORT_FILE


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    generate_report()
