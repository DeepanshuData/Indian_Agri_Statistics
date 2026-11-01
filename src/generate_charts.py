"""Generate high-resolution Rice summary charts from spatial analysis outputs."""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.pipeline_utils import CHART_OUTPUT, CSV_OUTPUT, ensure_output_directories


LOGGER = logging.getLogger("agri_gis.stage5")
UNITS_NOTE = "Source units are unverified"


def _save_chart(fig: plt.Figure, filename: str) -> None:
    fig.savefig(
        CHART_OUTPUT / filename,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    LOGGER.info("Saved chart: %s", CHART_OUTPUT / filename)


def _horizontal_bar(
    frame: pd.DataFrame,
    value_column: str,
    label_column: str,
    title: str,
    x_label: str,
    filename: str,
    *,
    color: str,
    value_format: str = "{:,.0f}",
) -> None:
    if frame.empty:
        raise ValueError(f"Cannot plot empty chart data for {filename}.")
    plot_data = frame.copy().sort_values(value_column, ascending=True)
    plot_data["plot_label"] = (
        plot_data[label_column].fillna("Unknown").astype(str)
        + " — "
        + plot_data["state"].fillna("Unknown").astype(str)
    )
    fig, axis = plt.subplots(figsize=(11, 7))
    bars = sns.barplot(
        data=plot_data,
        x=value_column,
        y="plot_label",
        color=color,
        ax=axis,
    )
    axis.set_title(title, fontsize=17, weight="bold", loc="left", pad=18)
    axis.set_xlabel(x_label, fontsize=11)
    axis.set_ylabel("")
    axis.grid(axis="x", linestyle="--", alpha=0.25)
    axis.set_axisbelow(True)
    sns.despine(ax=axis, left=True, bottom=True)
    maximum = float(plot_data[value_column].max())
    axis.set_xlim(0, maximum * 1.16 if maximum > 0 else 1)
    for patch, value in zip(bars.patches, plot_data[value_column]):
        axis.annotate(
            value_format.format(value),
            (patch.get_width(), patch.get_y() + patch.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
        )
    fig.text(0.01, 0.01, UNITS_NOTE, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save_chart(fig, filename)


def generate_charts(
    analysis: dict[str, pd.DataFrame] | None = None,
) -> list[str]:
    ensure_output_directories()
    sns.set_theme(style="whitegrid", context="notebook")
    if analysis is None:
        required_files = {
            "top_10_rice_production": "top_10_rice_production.csv",
            "top_10_rice_yield": "top_10_rice_yield.csv",
            "state_rice_analysis": "state_rice_analysis.csv",
            "rice_area_production_comparison": "rice_area_production_comparison.csv",
            "rice_yield_distribution": "rice_yield_distribution.csv",
        }
        missing = [
            name for name in required_files.values()
            if not (CSV_OUTPUT / name).is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "Spatial analysis outputs are missing: " + ", ".join(missing)
            )
        analysis = {
            key: pd.read_csv(CSV_OUTPUT / filename)
            for key, filename in required_files.items()
        }

    production = analysis["top_10_rice_production"]
    yields = analysis["top_10_rice_yield"]
    states = analysis["state_rice_analysis"]
    comparison = analysis["rice_area_production_comparison"]
    distribution = analysis["rice_yield_distribution"]

    _horizontal_bar(
        production,
        "total_production",
        "district",
        "Top 10 Rice-Producing Districts",
        "Total Rice production (source units unverified)",
        "top_10_rice_production.png",
        color="#2e7d32",
    )
    _horizontal_bar(
        yields,
        "crop_yield",
        "district",
        "Top 10 Districts by Rice Yield",
        "Production / area (source units unverified)",
        "top_10_rice_yield.png",
        color="#66a061",
        value_format="{:,.3f}",
    )

    state_yield = states.dropna(subset=["average_yield"]).sort_values(
        "average_yield", ascending=True
    )
    if state_yield.empty:
        raise ValueError("No valid state-level yields are available for charting.")
    fig, axis = plt.subplots(
        figsize=(11, max(7, len(state_yield) * 0.28))
    )
    sns.barplot(
        data=state_yield,
        x="average_yield",
        y="state",
        color="#4c956c",
        ax=axis,
    )
    axis.set_title("State-wise Area-weighted Average Rice Yield", loc="left", weight="bold")
    axis.set_xlabel("Total production / total area (units unverified)")
    axis.set_ylabel("")
    axis.grid(axis="x", linestyle="--", alpha=0.25)
    axis.set_axisbelow(True)
    sns.despine(ax=axis, left=True, bottom=True)
    fig.tight_layout()
    _save_chart(fig, "state_average_yield.png")

    state_production = states.sort_values("total_production", ascending=True)
    fig, axis = plt.subplots(
        figsize=(11, max(7, len(state_production) * 0.28))
    )
    sns.barplot(
        data=state_production,
        x="total_production",
        y="state",
        color="#277da1",
        ax=axis,
    )
    axis.set_title("Total Rice Production by State", loc="left", weight="bold")
    axis.set_xlabel("Total Rice production (source units unverified)")
    axis.set_ylabel("")
    axis.grid(axis="x", linestyle="--", alpha=0.25)
    axis.set_axisbelow(True)
    sns.despine(ax=axis, left=True, bottom=True)
    fig.tight_layout()
    _save_chart(fig, "state_production.png")

    if comparison.empty:
        raise ValueError("No district area/production comparisons are available.")
    scatter_data = comparison.dropna(
        subset=["total_area", "total_production"]
    ).copy()
    fig, axis = plt.subplots(figsize=(10, 7))
    sns.scatterplot(
        data=scatter_data,
        x="total_area",
        y="total_production",
        hue="state",
        alpha=0.8,
        s=55,
        palette="husl",
        legend=False,
        ax=axis,
    )
    axis.set_title("District Rice Area versus Production", loc="left", weight="bold")
    axis.set_xlabel("Total Rice area (source units unverified)")
    axis.set_ylabel("Total Rice production (source units unverified)")
    axis.grid(linestyle="--", alpha=0.25)
    fig.text(0.01, 0.01, UNITS_NOTE, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save_chart(fig, "area_vs_production.png")

    yield_data = distribution.dropna(subset=["crop_yield"])
    if yield_data.empty:
        raise ValueError("No valid district Rice yields are available for charting.")
    fig, axis = plt.subplots(figsize=(10, 7))
    sns.histplot(
        data=yield_data,
        x="crop_yield",
        bins="fd",
        kde=len(yield_data) > 2,
        color="#40916c",
        edgecolor="white",
        ax=axis,
    )
    axis.set_title("District-wise Rice Yield Distribution", loc="left", weight="bold")
    axis.set_xlabel("Production / area (source units unverified)")
    axis.set_ylabel("Number of districts")
    axis.grid(axis="y", linestyle="--", alpha=0.25)
    fig.text(0.01, 0.01, UNITS_NOTE, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save_chart(fig, "district_rice_yield_distribution.png")

    return [
        "top_10_rice_production.png",
        "top_10_rice_yield.png",
        "state_average_yield.png",
        "state_production.png",
        "area_vs_production.png",
        "district_rice_yield_distribution.png",
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    generate_charts()
