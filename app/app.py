from pathlib import Path
import re

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = [
    "state",
    "district",
    "crop",
    "year",
    "season",
    "area",
    "production",
    "yield",
]
FILTER_COLUMNS = ["state", "district", "crop", "season", "year"]
NUMERIC_COLUMNS = ["area", "production", "yield"]
ACCENT_GREEN = "#86b28b"
MUTED_GREEN = "#668d70"
TEXT_COLOR = "#e5ebe6"
GRID_COLOR = "#344139"
CHART_BACKGROUND = "#18211c"


st.set_page_config(
    page_title="Indian Agriculture Statistics",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

stylesheet_path = Path(__file__).with_name("styles.css")
if stylesheet_path.exists():
    st.markdown(
        f"<style>{stylesheet_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def find_dataset() -> Path | None:
    """Find the dataset while supporting the project's existing folder casing."""
    for relative_path in ("data/agridata.csv", "Data/agridata.csv"):
        candidate = PROJECT_ROOT / relative_path
        if candidate.is_file():
            return candidate
    return None


@st.cache_data(show_spinner="Loading agriculture dataset...")
def load_dataset(dataset_path: str) -> pd.DataFrame:
    """Load the CSV once and normalize analysis columns in memory."""
    dataframe = pd.read_csv(dataset_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe]
    if missing_columns:
        raise ValueError(", ".join(missing_columns))

    dataframe = dataframe[REQUIRED_COLUMNS].copy()
    for column in FILTER_COLUMNS:
        dataframe[column] = dataframe[column].astype("string").str.strip()
        dataframe[column] = dataframe[column].replace("", pd.NA)

    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

    return dataframe


def ordered_years(years: pd.Series) -> list[str]:
    """Return year labels in chronological order, excluding malformed labels."""
    valid_years = [
        str(year)
        for year in years.dropna().unique()
        if re.fullmatch(r"\d{4}(?:-\d{2})?", str(year))
    ]
    return sorted(valid_years, key=lambda year: (int(year[:4]), year))


def format_compact(value: float | int) -> str:
    """Format large totals compactly without inventing precision."""
    if pd.isna(value):
        return "—"
    magnitude = abs(value)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if magnitude >= threshold:
            return f"{value / threshold:,.1f}{suffix}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def chart_layout(figure: Figure, *, height: int = 420) -> None:
    """Apply shared visual settings to the Plotly charts."""
    figure.update_layout(
        height=height,
        margin=dict(l=12, r=18, t=18, b=12),
        paper_bgcolor=CHART_BACKGROUND,
        plot_bgcolor=CHART_BACKGROUND,
        font=dict(family="Arial, sans-serif", color=TEXT_COLOR, size=12),
        hoverlabel=dict(
            bgcolor="#203b2d",
            bordercolor="#203b2d",
            font=dict(color="white", size=12),
        ),
        showlegend=False,
    )
    figure.update_xaxes(
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
        tickfont=dict(color=TEXT_COLOR, size=11),
        title_font=dict(color=TEXT_COLOR),
    )
    figure.update_yaxes(
        showgrid=False,
        zeroline=False,
        tickfont=dict(color=TEXT_COLOR, size=11),
        title_font=dict(color=TEXT_COLOR),
    )


def available_options(dataframe: pd.DataFrame, column: str) -> list[str]:
    return sorted(str(value) for value in dataframe[column].dropna().unique())


dataset_path = find_dataset()
if dataset_path is None:
    st.error(
        "The agriculture dataset could not be found. Place agridata.csv in the "
        "project's data/ or Data/ folder."
    )
    st.stop()

try:
    dataset = load_dataset(str(dataset_path))
except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
    st.error(
        "The agriculture dataset could not be read. Check that the CSV is present "
        "and is a valid, UTF-8-compatible file."
    )
    st.stop()
except ValueError as error:
    st.error(
        "The agriculture dataset is missing required columns: "
        f"{error}. Expected: {', '.join(REQUIRED_COLUMNS)}."
    )
    st.stop()


with st.sidebar:
    st.markdown("### Data filters")
    st.caption(
        "Explore district-level crop statistics. Each selection updates the "
        "summary metrics, charts and records below."
    )

    state_options = available_options(dataset, "state")
    selected_state = st.selectbox("State", ["All"] + state_options)

    district_source = dataset
    if selected_state != "All":
        district_source = dataset.loc[dataset["state"] == selected_state]
    district_options = available_options(district_source, "district")
    selected_district = st.selectbox(
        "District",
        ["All"] + district_options,
        key=f"district_filter_{selected_state}",
    )

    crop_options = available_options(dataset, "crop")
    selected_crop = st.selectbox("Crop", ["All"] + crop_options)

    season_options = available_options(dataset, "season")
    selected_season = st.selectbox("Season", ["All"] + season_options)

    year_options = ordered_years(dataset["year"])
    selected_year = st.selectbox("Year", ["All"] + year_options)


st.title("Indian Agriculture Statistics")
st.markdown(
    '<p class="app-subtitle">A district-level view of crop area, production and '
    "yield across India.</p>",
    unsafe_allow_html=True,
)

filtered_data = dataset
for column, selected_value in (
    ("state", selected_state),
    ("district", selected_district),
    ("crop", selected_crop),
    ("season", selected_season),
    ("year", selected_year),
):
    if selected_value != "All":
        filtered_data = filtered_data.loc[filtered_data[column] == selected_value]
filtered_data = filtered_data.copy()

st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
st.subheader("Summary")

area_total = filtered_data["area"].sum(min_count=1)
production_total = filtered_data["production"].sum(min_count=1)
average_yield = filtered_data["yield"].mean()

kpi_columns = st.columns(4)
kpi_columns[0].metric("Total Area", format_compact(area_total))
kpi_columns[1].metric("Total Production", format_compact(production_total))
kpi_columns[2].metric(
    "Average Yield", "—" if pd.isna(average_yield) else f"{average_yield:,.2f}"
)
kpi_columns[3].metric("Number of Records", f"{len(filtered_data):,}")

if filtered_data.empty:
    st.info("No records match these filters. Adjust one or more selections to continue.")
else:
    state_area = (
        filtered_data.dropna(subset=["state", "area"])
        .groupby("state", as_index=False)["area"]
        .sum(min_count=1)
        .sort_values("area", ascending=False)
    )
    crop_production = (
        filtered_data.dropna(subset=["crop", "production"])
        .groupby("crop", as_index=False)["production"]
        .sum(min_count=1)
        .sort_values("production", ascending=False)
    )

    left_chart, right_chart = st.columns(2, gap="large")
    with left_chart:
        st.subheader("Crop Area by State")
        if state_area.empty:
            st.info("No area values are available for the selected records.")
        else:
            state_figure = px.bar(
                state_area,
                x="area",
                y="state",
                orientation="h",
                labels={"area": "Area", "state": ""},
                category_orders={"state": state_area["state"].tolist()},
                color_discrete_sequence=[ACCENT_GREEN],
                hover_data={"area": ":,.2f"},
            )
            state_figure.update_yaxes(autorange="reversed")
            state_figure.update_traces(
                hovertemplate="%{y}<br>Area: %{x:,.2f}<extra></extra>"
            )
            chart_layout(
                state_figure,
                height=max(440, min(680, 180 + len(state_area) * 15)),
            )
            st.plotly_chart(state_figure, use_container_width=True)

    with right_chart:
        st.subheader("Production by Crop")
        if crop_production.empty:
            st.info("No production values are available for the selected records.")
        else:
            production_figure = px.bar(
                crop_production,
                x="production",
                y="crop",
                orientation="h",
                labels={"production": "Production", "crop": ""},
                category_orders={"crop": crop_production["crop"].tolist()},
                color_discrete_sequence=[MUTED_GREEN],
                hover_data={"production": ":,.2f"},
            )
            production_figure.update_yaxes(autorange="reversed")
            production_figure.update_traces(
                hovertemplate="%{y}<br>Production: %{x:,.2f}<extra></extra>"
            )
            chart_layout(
                production_figure,
                height=max(440, min(680, 180 + len(crop_production) * 12)),
            )
            st.plotly_chart(production_figure, use_container_width=True)

    year_chart_data = filtered_data.dropna(subset=["year", "area"]).copy()
    year_chart_data["_year_start"] = pd.to_numeric(
        year_chart_data["year"].str.extract(r"^(\d{4})")[0], errors="coerce"
    )
    year_chart_data = year_chart_data.dropna(subset=["_year_start"])
    annual_area = (
        year_chart_data.groupby(["_year_start", "year"], as_index=False)["area"]
        .sum(min_count=1)
        .sort_values("_year_start")
    )

    st.subheader("Crop Area by Year")
    if annual_area.empty:
        st.info("No valid year and area values are available for the selected records.")
    else:
        annual_figure = px.line(
            annual_area,
            x="year",
            y="area",
            markers=True,
            labels={"year": "Year", "area": "Area"},
            color_discrete_sequence=[ACCENT_GREEN],
        )
        annual_figure.update_traces(
            line=dict(width=2),
            marker=dict(size=6),
            hovertemplate="%{x}<br>Area: %{y:,.2f}<extra></extra>",
        )
        chart_layout(annual_figure, height=390)
        annual_figure.update_layout(showlegend=False)
        st.plotly_chart(annual_figure, use_container_width=True)

    state_crop_area = (
        filtered_data.dropna(subset=["state", "crop", "area"])
        .groupby(["state", "crop"])["area"]
        .sum(min_count=1)
        .unstack(fill_value=0)
    )
    if not state_crop_area.empty:
        state_crop_area = state_crop_area.loc[
            state_crop_area.sum(axis=1).sort_values(ascending=False).index,
            state_crop_area.sum(axis=0).sort_values(ascending=False).index,
        ]

    st.subheader("State × Crop Area")
    if state_crop_area.empty:
        st.info("No state, crop and area combinations are available for the selection.")
    else:
        heatmap_figure = px.imshow(
            state_crop_area,
            labels={"x": "Crop", "y": "State", "color": "Area"},
            aspect="auto",
            color_continuous_scale=[
                "#202a23",
                "#536e58",
                "#86b28b",
                "#d6e5d4",
            ],
        )
        heatmap_figure.update_traces(
            hovertemplate="State: %{y}<br>Crop: %{x}<br>Area: %{z:,.2f}<extra></extra>"
        )
        heatmap_figure.update_xaxes(tickangle=-35)
        chart_layout(
            heatmap_figure,
            height=max(440, min(700, 220 + len(state_crop_area.index) * 14)),
        )
        heatmap_figure.update_layout(
            showlegend=False,
            coloraxis_colorbar=dict(title="Area"),
        )
        st.plotly_chart(heatmap_figure, use_container_width=True)

with st.expander("View filtered records"):
    st.dataframe(filtered_data, use_container_width=True, hide_index=True)
