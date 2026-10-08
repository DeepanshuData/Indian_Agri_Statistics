from pathlib import Path
import re

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
import requests
import streamlit as st

from market_engine import calculate_market_opportunity
from profitability_engine import calculate_profitability
from recommendation_engine import (
    canonical_crop_name,
    get_historical_crop_yields,
    recommend_crops,
)
from weather_engine import (
    calculate_weather_risk,
    geocode_location,
    get_weather_forecast,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = next(
    (
        directory
        for directory in (PROJECT_ROOT / "Data", PROJECT_ROOT / "data")
        if directory.is_dir()
    ),
    PROJECT_ROOT / "Data",
)
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


@st.cache_data(show_spinner="Loading reference data...")
def load_reference_data(reference_path: str) -> pd.DataFrame:
    return pd.read_csv(reference_path)


def format_currency(value: float | int) -> str:
    return f"₹{value:,.0f}"


def crops_with_economics(
    crops: list[str], economics: pd.DataFrame
) -> list[str]:
    economic_names = {
        canonical_crop_name(crop) for crop in economics["crop"].dropna()
    }
    return [
        crop
        for crop in crops
        if canonical_crop_name(crop) in economic_names
    ]


@st.cache_data(ttl=1800, show_spinner=False)
def cached_geocode_location(district: str, state: str) -> dict | None:
    return geocode_location(district, state)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_weather_forecast(latitude: float, longitude: float) -> dict:
    return get_weather_forecast(latitude, longitude)


def weather_for_location(state: str, district: str) -> tuple[dict, dict]:
    location = cached_geocode_location(district, state)
    if location is None:
        raise ValueError(
            f"No coordinates were found for {district}, {state}. "
            "Try another district or continue without weather scoring."
        )
    forecast = cached_weather_forecast(
        location["latitude"], location["longitude"]
    )
    return location, forecast


def render_crop_recommendations(dataframe: pd.DataFrame, economics: pd.DataFrame) -> None:
    st.header("What Should I Grow?")
    st.caption(
        "Rank crops using district-season yield history, estimated economics, "
        "irrigation fit and an optional 5-day weather risk adjustment."
    )

    state_options = available_options(dataframe, "state")
    state = st.selectbox("State", state_options, key="grow_state")
    state_data = dataframe.loc[dataframe["state"] == state]
    district_options = available_options(state_data, "district")
    district = st.selectbox("District", district_options, key="grow_district")
    district_data = state_data.loc[state_data["district"] == district]
    seasons = ["All"] + available_options(district_data, "season")

    input_columns = st.columns(4)
    with input_columns[0]:
        season = st.selectbox("Season", seasons, key="grow_season")
    with input_columns[1]:
        land_acres = st.number_input(
            "Land (acres)", min_value=0.1, value=1.0, step=0.5, key="grow_land"
        )
    with input_columns[2]:
        budget = st.number_input(
            "Budget (₹)", min_value=0.0, value=100000.0, step=10000.0,
            key="grow_budget",
        )
    with input_columns[3]:
        irrigation = st.selectbox(
            "Irrigation", ["No", "Partial", "Yes"], key="grow_irrigation"
        )

    include_weather = st.checkbox(
        "Include current 5-day weather risk in ranking",
        value=True,
        key="grow_weather",
    )
    if st.button("Rank suitable crops", type="primary", key="rank_crops"):
        weather_risk = None
        if include_weather:
            try:
                with st.spinner("Checking district forecast..."):
                    _, forecast = weather_for_location(state, district)
                weather_risk = calculate_weather_risk(forecast)["Risk"]
                st.caption(f"Forecast weather risk included: **{weather_risk}**")
            except requests.RequestException as error:
                st.error(f"Weather service request failed: {error}")
                return
            except ValueError as error:
                st.error(str(error))
                return

        results = recommend_crops(
            dataframe,
            economics,
            district,
            land_acres,
            budget,
            irrigation,
            season,
            weather_risk,
        )
        if results.empty:
            st.info(
                "No crop has both matching historical yield and economics within "
                "this budget. Try a larger budget, another season or another district."
            )
        else:
            st.subheader("Crop ranking")
            st.dataframe(
                results.drop(columns=["Score"]),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Ranking combines estimated ROI with crop risk; an included "
                "medium/high weather risk applies an additional ranking penalty. "
                "Economics are reference estimates from the supplied crop data."
            )


def render_profitability(dataframe: pd.DataFrame, economics: pd.DataFrame) -> None:
    st.header("Profitability")
    st.caption(
        "Estimate revenue, cost, profit, ROI and crop price risk using historical "
        "yield for a selected district and season."
    )

    state_options = available_options(dataframe, "state")
    state = st.selectbox("State", state_options, key="profit_state")
    state_data = dataframe.loc[dataframe["state"] == state]
    district_options = available_options(state_data, "district")
    district = st.selectbox("District", district_options, key="profit_district")
    district_data = state_data.loc[state_data["district"] == district]
    season_options = ["All"] + available_options(district_data, "season")
    season = st.selectbox("Season", season_options, key="profit_season")
    yields = get_historical_crop_yields(dataframe, district, season)
    crops = crops_with_economics(
        available_options(yields, "crop") if not yields.empty else [],
        economics,
    )
    if not crops:
        st.info(
            "No crops in this district and season have both yield history and "
            "reference economics."
        )
        return

    crop = st.selectbox("Crop", crops, key="profit_crop")
    historical_yield = float(
        yields.loc[yields["crop"] == crop, "historical_yield"].iloc[0]
    )
    crop_economics = economics.loc[
        economics["crop"].map(canonical_crop_name) == canonical_crop_name(crop)
    ].iloc[0]
    st.metric("Historical average yield", f"{historical_yield:,.2f} tonnes/hectare")

    input_columns = st.columns(3)
    with input_columns[0]:
        land_acres = st.number_input(
            "Land (acres)", min_value=0.1, value=1.0, step=0.5, key="profit_land"
        )
    with input_columns[1]:
        price_per_kg = st.number_input(
            "Price (₹/kg)",
            min_value=0.0,
            value=float(crop_economics["price_per_kg"]),
            step=1.0,
            key="profit_price",
        )
    with input_columns[2]:
        cost_per_acre = st.number_input(
            "Cost (₹/acre)",
            min_value=0.0,
            value=float(crop_economics["cost_per_acre"]),
            step=1000.0,
            key="profit_cost",
        )

    if st.button("Calculate profitability", type="primary", key="calculate_profit"):
        result = calculate_profitability(
            crop,
            land_acres,
            historical_yield,
            economics,
            price_per_kg=price_per_kg,
            cost_per_acre=cost_per_acre,
        )
        if result is None:
            st.error("Economics are not available for the selected crop.")
            return

        metric_columns = st.columns(4)
        metric_columns[0].metric(
            "Expected revenue", format_currency(result["Expected Revenue"])
        )
        metric_columns[1].metric(
            "Estimated cost", format_currency(result["Estimated Cost"])
        )
        metric_columns[2].metric(
            "Expected profit", format_currency(result["Expected Profit"])
        )
        metric_columns[3].metric("ROI", f'{result["ROI (%)"]:,.1f}%')
        st.info(
            f'Estimated production: {result["Expected Production (tonnes)"]:,.2f} tonnes'
            f'  ·  Risk: {result["Risk"]}  ·  Price volatility: '
            f'{result["Price Volatility"]:.0%}  ·  Water requirement: '
            f'{result["Water Requirement"]}'
        )
        st.caption(
            "Yield is the historical district-season mean in the agriculture data. "
            "Price and cost are editable assumptions; actual outcomes vary."
        )


def render_market_finder(market_data: pd.DataFrame) -> None:
    st.header("Where Should I Sell?")
    st.caption(
        "Compare the supplied destination-market price and transport estimates "
        "for your crop, origin and sale quantity."
    )
    crops = available_options(market_data, "crop")
    if not crops:
        st.info("No market price data is currently available.")
        return

    crop = st.selectbox("Crop", crops, key="market_crop")
    crop_data = market_data.loc[market_data["crop"] == crop]
    origins = available_options(crop_data, "origin_market")
    if not origins:
        st.info(f"No origin markets are listed for {crop}.")
        return
    origin = st.selectbox("Origin", origins, key="market_origin")
    quantity_tonnes = st.number_input(
        "Quantity (tonnes)",
        min_value=0.01,
        value=1.0,
        step=0.5,
        key="market_quantity",
    )

    if st.button("Compare markets", type="primary", key="compare_markets"):
        results = calculate_market_opportunity(
            market_data, crop, origin, quantity_tonnes
        )
        if results.empty:
            st.info("There are no destination price records for this selection.")
            return
        best_market = results.iloc[0]
        st.success(
            f'Best listed market: **{best_market["destination_market"]}** — '
            f'net realization {format_currency(best_market["Net Realization"])} '
            f'({format_currency(best_market["Net Price per Kg"])}/kg)'
        )
        display = results[
            [
                "destination_market",
                "current_price_per_kg",
                "distance_km",
                "Transport Cost",
                "Net Price per Kg",
                "Net Realization",
            ]
        ].rename(
            columns={
                "destination_market": "Destination",
                "current_price_per_kg": "Market price (₹/kg)",
                "distance_km": "Distance (km)",
                "Transport Cost": "Transport cost (₹)",
                "Net Price per Kg": "Net price (₹/kg)",
                "Net Realization": "Net realization (₹)",
            }
        )
        st.dataframe(display, width="stretch", hide_index=True)
        st.caption(
            "This comparison only covers destinations present in the supplied "
            "market data. Treat these as reference prices and transport estimates, "
            "not live quotes."
        )


def render_weather_risk(dataframe: pd.DataFrame) -> None:
    st.header("Weather Risk")
    st.caption(
        "Fetch a 5-day Open-Meteo forecast for a district and summarize rainfall, "
        "rain probability and a simple weather-risk category."
    )
    state_options = available_options(dataframe, "state")
    state = st.selectbox("State", state_options, key="weather_state")
    state_data = dataframe.loc[dataframe["state"] == state]
    district_options = available_options(state_data, "district")
    district = st.selectbox("District", district_options, key="weather_district")

    if st.button("Get 5-day forecast", type="primary", key="get_forecast"):
        try:
            with st.spinner("Finding district coordinates and loading forecast..."):
                location, forecast = weather_for_location(state, district)
            daily = forecast["daily"]
            risk = calculate_weather_risk(forecast)
        except requests.RequestException as error:
            st.error(f"Weather service request failed: {error}")
            return
        except ValueError as error:
            st.error(str(error))
            return

        st.caption(
            f'Forecast location: {location["name"]} '
            f'({location["latitude"]:.3f}, {location["longitude"]:.3f})'
        )
        metric_columns = st.columns(3)
        metric_columns[0].metric(
            "5-day rainfall", f'{risk["Total 5-Day Rainfall"]:,.1f} mm'
        )
        metric_columns[1].metric(
            "Maximum rain probability",
            f'{risk["Maximum Rain Probability"]}%'
        )
        metric_columns[2].metric("Weather risk", risk["Risk"])

        daily_forecast = pd.DataFrame(
            {
                "Date": daily["time"],
                "Maximum temperature (°C)": daily["temperature_2m_max"],
                "Minimum temperature (°C)": daily["temperature_2m_min"],
                "Rainfall (mm)": daily["precipitation_sum"],
                "Rain probability (%)": daily["precipitation_probability_max"],
            }
        )
        st.dataframe(daily_forecast, width="stretch", hide_index=True)
        st.caption(
            "Risk bands use the engine's rainfall thresholds (50/100 mm total) "
            "and maximum rain-probability thresholds (60/80%). Forecasts are "
            "informational and can change."
        )


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
    selected_tool = st.selectbox(
        "Agriculture tools",
        [
            "Dashboard",
            "What Should I Grow?",
            "Profitability",
            "Where Should I Sell?",
            "Weather Risk",
        ],
    )
    if selected_tool == "Dashboard":
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

if selected_tool != "Dashboard":
    if selected_tool in ("What Should I Grow?", "Profitability"):
        reference_file = DATA_DIRECTORY / "crop_economics.csv"
    elif selected_tool == "Where Should I Sell?":
        reference_file = DATA_DIRECTORY / "market_data.csv"
    else:
        reference_file = None

    reference_data = None
    if reference_file is not None:
        try:
            reference_data = load_reference_data(str(reference_file))
        except (
            OSError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
            UnicodeDecodeError,
        ) as error:
            st.error(f"Could not load {reference_file.name}: {error}")
            st.stop()

    if selected_tool == "What Should I Grow?":
        render_crop_recommendations(dataset, reference_data)
    elif selected_tool == "Profitability":
        render_profitability(dataset, reference_data)
    elif selected_tool == "Where Should I Sell?":
        render_market_finder(reference_data)
    else:
        render_weather_risk(dataset)
    st.stop()

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
            st.plotly_chart(state_figure, width="stretch")

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
            st.plotly_chart(production_figure, width="stretch")

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
        st.plotly_chart(annual_figure, width="stretch")

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
        st.plotly_chart(heatmap_figure, width="stretch")

with st.expander("View filtered records"):
    st.dataframe(filtered_data, width="stretch", hide_index=True)
