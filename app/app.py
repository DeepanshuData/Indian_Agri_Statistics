from pathlib import Path
from html import escape
import re
import json
import base64

import numpy as np
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objects import Figure
from plotly.subplots import make_subplots
import requests
import streamlit as st
from shapely.geometry import mapping, shape

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
    normalize_location_name,
    normalize_state_name,
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
ACCENT_GREEN = "#a7c4a0"
MUTED_GREEN = "#6f9a78"
TEXT_COLOR = "#e8eee8"
GRID_COLOR = "#304237"
CHART_BACKGROUND = "#18251d"


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
        font=dict(family="sans-serif", color=TEXT_COLOR, size=12),
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


def render_page_header(title: str, description: str, section: str) -> None:
    st.markdown(
        f'<div class="page-heading"><div class="page-eyebrow">{section}</div>'
        f'<h1 class="page-title">{title}</h1>'
        f'<p class="page-description">{description}</p></div>',
        unsafe_allow_html=True,
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
    return geocode_location(district.strip(), state.strip())


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
    render_page_header(
        "What Should I Grow?",
        "Rank crops using district-season yield history, estimated economics, "
        "irrigation fit and an optional 5-day weather risk adjustment.",
        "Crop intelligence",
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
                    location, forecast = weather_for_location(state, district)
                weather_risk = calculate_weather_risk(forecast)["Risk"]
                st.caption(f"Forecast weather risk included: **{weather_risk}**")
                if location.get("precision", "district") == "state":
                    st.warning(
                        "District coordinates were unavailable. Crop ranking is "
                        "using an approximate state-level weather forecast."
                    )
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
            top_crop = results.iloc[0]
            st.subheader("Top-ranked option")
            st.markdown(
                f"### {top_crop['Crop']}"
                f"  \nRisk: **{top_crop['Risk']}**"
            )
            result_columns = st.columns(3)
            result_columns[0].metric(
                "Expected profit", format_currency(top_crop["Expected Profit"])
            )
            result_columns[1].metric(
                "Historical yield",
                f"{top_crop['Historical Yield']:,.2f} tonnes/hectare",
            )
            result_columns[2].metric("Estimated ROI", f"{top_crop['ROI (%)']:,.1f}%")
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
    render_page_header(
        "Profitability",
        "Estimate revenue, cost, profit, ROI and crop price risk using historical "
        "yield for a selected district and season.",
        "Crop intelligence",
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
    st.markdown(
        '<div class="market-page-header"><div><div class="page-eyebrow">'
        'MARKET INTELLIGENCE</div><h1 class="page-title">'
        "Where Should I Sell?</h1><p class=\"page-description\">"
        "Compare destination prices and estimated transport costs to find the "
        "strongest listed net return for your crop.</p></div>"
        '<div class="market-live-badge"><span></span> REFERENCE MARKET DATA</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    crops = available_options(market_data, "crop")
    if not crops:
        st.info("No market price data is currently available.")
        return

    input_columns = st.columns([1.2, 1.2, 1, 1.2], gap="small")
    crop = input_columns[0].selectbox("Crop", crops, key="market_crop")
    crop_data = market_data.loc[market_data["crop"] == crop]
    origins = available_options(crop_data, "origin_market")
    if not origins:
        st.info(f"No origin markets are listed for {crop}.")
        return
    origin = input_columns[1].selectbox("Origin market", origins, key="market_origin")
    quantity_tonnes = input_columns[2].number_input(
        "Quantity (tonnes)",
        min_value=0.01,
        value=20.0,
        step=0.5,
        key="market_quantity",
    )
    input_columns[3].markdown(
        '<div class="market-data-stamp"><span>DATA BASIS</span>'
        '<strong>Supplied reference prices</strong></div>',
        unsafe_allow_html=True,
    )

    results = calculate_market_opportunity(
        market_data, crop, origin, quantity_tonnes
    )
    if results.empty:
        st.info("There are no destination price records for this selection.")
        return

    best_market = results.iloc[0]
    market_count = len(results)
    average_price = results["current_price_per_kg"].mean()
    average_transport = results["transport_cost_per_kg"].mean() * 1000
    summary_columns = st.columns(4, gap="small")
    summary_columns[0].metric(
        "Best market · net return",
        str(best_market["destination_market"]),
        delta=f'₹{best_market["Net Realization"]:,.0f} total',
        help="Ranked by estimated net realization for the selected quantity.",
    )
    summary_columns[1].metric(
        "Average market price",
        f"₹{average_price:,.2f}/kg",
        help="Mean listed price across the selected crop's destinations.",
    )
    summary_columns[2].metric(
        "Average transport cost",
        f"₹{average_transport:,.0f}/tonne",
        help="Mean supplied transport rate across destinations, scaled to one tonne.",
    )
    summary_columns[3].metric(
        "Estimated net return",
        format_currency(best_market["Net Realization"]),
        help=f"Estimated for {quantity_tonnes:,.1f} tonnes.",
    )

    st.markdown(
        '<div class="section-heading market-section-heading">'
        '<div><div class="section-kicker">DESTINATION ANALYSIS</div>'
        '<h2 class="section-title">Price, distance & net realization</h2></div>'
        f'<div class="section-note">{escape(crop)} · {quantity_tonnes:,.1f} tonnes '
        f'from {escape(origin)} · {market_count} markets</div></div>',
        unsafe_allow_html=True,
    )
    analysis_columns = st.columns([1.05, 1.15], gap="medium")
    with analysis_columns[0]:
        st.markdown(
            '<div class="market-card-heading">NET RETURN BY DESTINATION</div>',
            unsafe_allow_html=True,
        )
        return_figure = px.bar(
            results.sort_values("Net Realization"),
            x="Net Realization",
            y="destination_market",
            orientation="h",
            labels={
                "Net Realization": "Estimated net realization (₹)",
                "destination_market": "",
            },
            color_discrete_sequence=["#67c88d"],
            hover_data={
                "distance_km": ":,.0f",
                "Net Price per Kg": ":,.2f",
            },
        )
        chart_layout(return_figure, height=max(300, min(500, 190 + market_count * 46)))
        return_figure.update_traces(
            hovertemplate="%{y}<br>Net return: ₹%{x:,.0f}<extra></extra>"
        )
        return_figure.update_xaxes(title="Estimated net return (₹)")
        return_figure.update_yaxes(autorange="reversed")
        st.plotly_chart(return_figure, width="stretch")

        price_figure = px.bar(
            results.sort_values("current_price_per_kg", ascending=False),
            x="destination_market",
            y="current_price_per_kg",
            labels={
                "current_price_per_kg": "Listed price (₹/kg)",
                "destination_market": "",
            },
            color_discrete_sequence=["#86b8a0"],
        )
        chart_layout(price_figure, height=260)
        price_figure.update_xaxes(tickangle=-25)
        st.plotly_chart(price_figure, width="stretch")
    with analysis_columns[1]:
        st.markdown(
            '<div class="market-card-heading">MARKET COMPARISON</div>',
            unsafe_allow_html=True,
        )
        display = results[
            [
                "destination_market",
                "distance_km",
                "current_price_per_kg",
                "transport_cost_per_kg",
                "Transport Cost",
                "Net Realization",
            ]
        ].rename(
            columns={
                "destination_market": "Destination",
                "distance_km": "Distance (km)",
                "current_price_per_kg": "Price (₹/kg)",
                "transport_cost_per_kg": "Transport (₹/kg)",
                "Transport Cost": "Total transport (₹)",
                "Net Realization": "Net return (₹)",
            }
        )
        display.insert(0, "Rank", range(1, len(display) + 1))
        st.dataframe(display, width="stretch", hide_index=True)
        runner_up = results.iloc[1] if market_count > 1 else None
        insight = (
            f'{best_market["destination_market"]} ranks first for this selection. '
            f'Its listed distance is {best_market["distance_km"]:,.0f} km and its '
            f'estimated net price is ₹{best_market["Net Price per Kg"]:,.2f}/kg.'
        )
        if runner_up is not None:
            difference = best_market["Net Realization"] - runner_up["Net Realization"]
            insight += (
                f' That is ₹{difference:,.0f} more than '
                f'{runner_up["destination_market"]}.'
            )
        st.markdown(
            f'<div class="market-insight"><div class="market-card-heading">'
            f"TOP MARKET INSIGHT</div><p>{escape(insight)}</p></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "This view uses only destinations in the supplied reference file. "
            "Prices and transport estimates are not live quotes."
        )


def render_weather_risk(dataframe: pd.DataFrame) -> None:
    st.markdown(
        '<div class="weather-page-header"><div><div class="page-eyebrow">'
        'FIELD CONDITIONS</div><h1 class="page-title">Weather Risk</h1>'
        '<p class="page-description">A five-day outlook for a selected district, '
        "with rainfall, temperature, and precipitation risk at a glance.</p></div>"
        '<div class="weather-source-badge">OPEN-METEO · 5-DAY OUTLOOK</div></div>',
        unsafe_allow_html=True,
    )
    state_options = available_options(dataframe, "state")
    selected_location = st.columns([1, 1, 1.6], gap="small")
    state = selected_location[0].selectbox(
        "State", state_options, key="weather_state"
    )
    state_data = dataframe.loc[dataframe["state"] == state]
    district_options = available_options(state_data, "district")
    district = selected_location[1].selectbox(
        "District", district_options, key="weather_district"
    )
    if selected_location[2].button(
        "Load district forecast", type="primary", key="get_forecast"
    ):
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

        st.session_state["weather_last_forecast"] = {
            "state": state,
            "district": district,
            "location": location,
            "forecast": forecast,
            "risk": risk,
        }
    saved_forecast = st.session_state.get("weather_last_forecast")
    if not saved_forecast:
        st.info("Choose a state and district, then load the latest five-day forecast.")
        return
    if (
        saved_forecast["state"] != state
        or saved_forecast["district"] != district
    ):
        st.info("Load the forecast for the newly selected district.")
        return

    location = saved_forecast["location"]
    forecast = saved_forecast["forecast"]
    daily = forecast["daily"]
    risk = saved_forecast["risk"]
    st.markdown(
        f'<div class="weather-location-strip"><div><span>FORECAST AREA</span>'
        f'<strong>{escape(location["name"])}</strong></div>'
        f'<div><span>COORDINATES</span><strong>'
        f'{location["latitude"]:.3f}, {location["longitude"]:.3f}'
        f"</strong></div></div>",
        unsafe_allow_html=True,
    )
    if location.get("precision", "district") == "state":
        st.warning(
            "District coordinates were unavailable. This is an approximate "
            "state-level forecast, not a district-specific forecast."
        )
    total_rain = risk["Total 5-Day Rainfall"]
    average_high = float(np.mean(daily["temperature_2m_max"]))
    max_probability = risk["Maximum Rain Probability"]
    risk_class = str(risk["Risk"]).lower()
    st.markdown(
        f'<div class="weather-risk-banner risk-{risk_class}">'
        f'<div><span>FIVE-DAY WEATHER RISK</span><strong>{escape(risk["Risk"])}</strong>'
        f"</div><p>Based on forecast rainfall and maximum precipitation probability "
        f"for {escape(district)}, {escape(state)}.</p></div>",
        unsafe_allow_html=True,
    )
    metric_columns = st.columns(4, gap="small")
    metric_columns[0].metric("Total rainfall", f"{total_rain:,.1f} mm")
    metric_columns[1].metric("Peak rain probability", f"{max_probability}%")
    metric_columns[2].metric("Average daily high", f"{average_high:,.1f} °C")
    metric_columns[3].metric("Forecast days", f"{len(daily['time'])}")
    daily_forecast = pd.DataFrame(
        {
            "Date": daily["time"],
            "Maximum temperature (°C)": daily["temperature_2m_max"],
            "Minimum temperature (°C)": daily["temperature_2m_min"],
            "Rainfall (mm)": daily["precipitation_sum"],
            "Rain probability (%)": daily["precipitation_probability_max"],
        }
    )
    forecast_figure = make_subplots(specs=[[{"secondary_y": True}]])
    forecast_figure.add_trace(
        go.Scatter(
            x=daily_forecast["Date"],
            y=daily_forecast["Maximum temperature (°C)"],
            mode="lines+markers",
            name="Maximum temperature",
            line=dict(color="#a9dcad", width=3),
        ),
        secondary_y=False,
    )
    forecast_figure.add_trace(
        go.Scatter(
            x=daily_forecast["Date"],
            y=daily_forecast["Minimum temperature (°C)"],
            mode="lines+markers",
            name="Minimum temperature",
            line=dict(color="#e3c77a", width=2),
        ),
        secondary_y=False,
    )
    forecast_figure.add_trace(
        go.Bar(
            x=daily_forecast["Date"],
            y=daily_forecast["Rainfall (mm)"],
            name="Rainfall",
            marker_color="#5ba4ae",
            opacity=0.55,
        ),
        secondary_y=True,
    )
    forecast_figure.update_yaxes(title_text="Temperature (°C)", secondary_y=False)
    forecast_figure.update_yaxes(title_text="Rainfall (mm)", secondary_y=True)
    forecast_figure.update_layout(
        barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    chart_layout(forecast_figure, height=360)
    forecast_figure.update_layout(showlegend=True)
    forecast_columns = st.columns([1.6, 0.9], gap="medium")
    with forecast_columns[0]:
        st.markdown(
            '<div class="market-card-heading">FIVE-DAY FORECAST</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(forecast_figure, width="stretch")
    with forecast_columns[1]:
        st.markdown(
            '<div class="market-card-heading">DAILY CONDITIONS</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(daily_forecast, width="stretch", hide_index=True)
        st.caption(
            "Risk bands use the weather engine's rainfall thresholds (50/100 mm "
            "total) and maximum rain-probability thresholds (60/80%). Forecasts "
            "are informational and can change."
        )


@st.cache_data(show_spinner="Loading district locations...")
def load_district_coordinates(coordinates_path: str) -> pd.DataFrame:
    coordinates = pd.read_csv(coordinates_path)
    required_columns = {"state", "district", "latitude", "longitude", "precision"}
    missing_columns = required_columns.difference(coordinates.columns)
    if missing_columns:
        raise ValueError(", ".join(sorted(missing_columns)))
    coordinates = coordinates.loc[
        coordinates["precision"] == "district",
        ["state", "district", "latitude", "longitude"],
    ].copy()
    coordinates["latitude"] = pd.to_numeric(
        coordinates["latitude"], errors="coerce"
    )
    coordinates["longitude"] = pd.to_numeric(
        coordinates["longitude"], errors="coerce"
    )
    coordinates = coordinates.dropna(
        subset=["state", "district", "latitude", "longitude"]
    )
    coordinates["_location_key"] = [
        spatial_location_key(state, district)
        for state, district in zip(coordinates["state"], coordinates["district"])
    ]
    return coordinates.drop_duplicates("_location_key")


def render_crop_dna(
    dataframe: pd.DataFrame, economics: pd.DataFrame | None = None
) -> None:
    st.markdown(
        '<div class="crop-dna-header"><div><div class="page-eyebrow">'
        'CROP & FIELD INTELLIGENCE</div><h1 class="page-title">Crop DNA</h1>'
        '<p class="page-description">Explore evidence-based crop profiles and '
        "district-level field signals from the records available in this project."
        "</p></div><div class=\"crop-data-badge\">HISTORICAL DATA · INDIA</div></div>",
        unsafe_allow_html=True,
    )
    crop_tab, field_tab = st.tabs(["Crop profile", "Field monitoring"])

    with crop_tab:
        profile_columns = st.columns([1.1, 1.1, 1, 1.1], gap="small")
        crop = profile_columns[0].selectbox(
            "Crop", available_options(dataframe, "crop"), key="crop_dna_crop"
        )
        state = profile_columns[1].selectbox(
            "State / territory",
            ["All India"] + available_options(dataframe, "state"),
            key="crop_dna_state",
        )
        crop_rows = dataframe.loc[dataframe["crop"] == crop]
        if state != "All India":
            crop_rows = crop_rows.loc[crop_rows["state"] == state]
        season = profile_columns[2].selectbox(
            "Season",
            ["All seasons"] + available_options(crop_rows, "season"),
            key="crop_dna_season",
        )
        if season != "All seasons":
            crop_rows = crop_rows.loc[crop_rows["season"] == season]
        year_options = ordered_years(crop_rows["year"])
        year = profile_columns[3].selectbox(
            "Year",
            ["All years"] + year_options,
            key="crop_dna_year",
        )
        if year != "All years":
            crop_rows = crop_rows.loc[crop_rows["year"] == year]

        valid_yield = crop_rows.dropna(subset=["area", "yield"]).loc[
            lambda rows: rows["area"] > 0
        ]
        valid_area = valid_yield["area"].sum(min_count=1)
        weighted_yield = (
            (valid_yield["area"] * valid_yield["yield"]).sum() / valid_area
            if pd.notna(valid_area) and valid_area > 0
            else float("nan")
        )
        area_total = crop_rows["area"].sum(min_count=1)
        production_total = crop_rows["production"].sum(min_count=1)
        state_count = crop_rows["state"].nunique()

        st.markdown(
            '<div class="crop-data-notice"><strong>What “Crop DNA” means here'
            "</strong><span>These are historical crop-performance profiles, not "
            "genetic or genomic traits. The project does not include genomic, "
            "soil-sensor, or field-imagery records.</span></div>",
            unsafe_allow_html=True,
        )
        metrics = st.columns(4, gap="small")
        metrics[0].metric(
            "Area-weighted yield",
            "—" if pd.isna(weighted_yield) else f"{weighted_yield:,.2f} t/ha",
        )
        metrics[1].metric("Recorded area", format_compact(area_total) + " ha")
        metrics[2].metric(
            "Recorded production", format_compact(production_total) + " t"
        )
        metrics[3].metric("Reporting states", f"{state_count:,}")

        reference = None
        if economics is not None and not economics.empty:
            matching = economics.loc[
                economics["crop"].map(canonical_crop_name)
                == canonical_crop_name(crop)
            ]
            if not matching.empty:
                reference = matching.iloc[0]
        if reference is not None:
            traits = st.columns(4, gap="small")
            traits[0].metric("Reference water need", str(reference["water_requirement"]))
            traits[1].metric(
                "Reference cost", f'₹{reference["cost_per_acre"]:,.0f}/acre'
            )
            traits[2].metric("Reference price", f'₹{reference["price_per_kg"]:,.0f}/kg')
            traits[3].metric(
                "Price volatility",
                f'{reference["price_volatility"]:.0%}',
                help="Supplied crop-economics reference, not a forecast.",
            )
        else:
            st.info("No crop-economics reference is available for this crop.")

        analysis = st.columns([1.2, 0.8], gap="medium")
        with analysis[0]:
            st.markdown(
                '<div class="market-card-heading">RECORDED YIELD TREND</div>',
                unsafe_allow_html=True,
            )
            trend = crop_rows.dropna(subset=["year", "yield"]).copy()
            trend["_year_number"] = pd.to_numeric(
                trend["year"].str.extract(r"^(\d{4})")[0], errors="coerce"
            )
            trend = trend.dropna(subset=["_year_number"])
            trend["_weighted_yield_area"] = trend["area"].where(
                trend["area"].gt(0), 0
            )
            trend["_weighted_yield_value"] = (
                trend["_weighted_yield_area"] * trend["yield"]
            )
            annual = (
                trend.groupby(["_year_number", "year"], as_index=False)
                .agg(
                    weighted_yield_value=("_weighted_yield_value", "sum"),
                    weighted_yield_area=("_weighted_yield_area", "sum"),
                )
            )
            annual["weighted_yield"] = (
                annual["weighted_yield_value"]
                / annual["weighted_yield_area"].replace(0, np.nan)
            )
            annual = annual.sort_values("_year_number")
            if annual.empty:
                st.info("No year-by-year yield records match this crop selection.")
            else:
                yield_figure = px.line(
                    annual,
                    x="year",
                    y="weighted_yield",
                    markers=True,
                    labels={"year": "Reporting year", "weighted_yield": "Yield (t/ha)"},
                    color_discrete_sequence=["#80d59b"],
                )
                chart_layout(yield_figure, height=330)
                st.plotly_chart(yield_figure, width="stretch")
        with analysis[1]:
            st.markdown(
                '<div class="market-card-heading">LEADING STATES BY AREA</div>',
                unsafe_allow_html=True,
            )
            leaders = (
                crop_rows.dropna(subset=["state", "area"])
                .groupby("state", as_index=False)["area"]
                .sum(min_count=1)
                .sort_values("area", ascending=False)
                .head(8)
                .sort_values("area")
            )
            if leaders.empty:
                st.info("No state area records are available for this selection.")
            else:
                leaders_figure = px.bar(
                    leaders,
                    x="area",
                    y="state",
                    orientation="h",
                    labels={"area": "Area (ha)", "state": ""},
                    color_discrete_sequence=["#5da779"],
                )
                leaders_figure.update_yaxes(autorange="reversed")
                chart_layout(leaders_figure, height=330)
                st.plotly_chart(leaders_figure, width="stretch")

    with field_tab:
        st.markdown(
            '<div class="crop-data-notice"><strong>District-level monitoring'
            "</strong><span>Markers represent district coordinate records and "
            "agricultural statistics. They are not farm boundaries or live "
            "satellite/sensor measurements.</span></div>",
            unsafe_allow_html=True,
        )
        filters = st.columns([1.1, 1.2, 1.2, 0.95], gap="small")
        states = available_options(dataframe, "state")
        field_state = filters[0].selectbox(
            "State", states, key="field_monitor_state"
        )
        state_rows = dataframe.loc[dataframe["state"] == field_state]
        field_districts = filters[1].selectbox(
            "District",
            ["All districts"] + available_options(state_rows, "district"),
            key="field_monitor_district",
        )
        field_crops = filters[2].selectbox(
            "Crop",
            ["All crops"] + available_options(state_rows, "crop"),
            key="field_monitor_crop",
        )
        field_years = ["All years"] + ordered_years(state_rows["year"])
        field_year = filters[3].selectbox(
            "Year", field_years, key="field_monitor_year"
        )

        field_rows = state_rows
        if field_districts != "All districts":
            field_rows = field_rows.loc[field_rows["district"] == field_districts]
        if field_crops != "All crops":
            field_rows = field_rows.loc[field_rows["crop"] == field_crops]
        if field_year != "All years":
            field_rows = field_rows.loc[field_rows["year"] == field_year]
        district_summary = (
            field_rows.groupby(["state", "district"], as_index=False)
            .agg(
                area=("area", lambda values: values.sum(min_count=1)),
                production=("production", lambda values: values.sum(min_count=1)),
                record_count=("crop", "size"),
            )
        )
        if district_summary.empty:
            st.info("No district-level agriculture records match these filters.")
            return
        district_summary["location_key"] = [
            spatial_location_key(state_name, district_name)
            for state_name, district_name in zip(
                district_summary["state"], district_summary["district"]
            )
        ]
        try:
            coordinates = load_district_coordinates(
                str(DATA_DIRECTORY / "district_coordinates.csv")
            )
        except (OSError, pd.errors.ParserError, ValueError) as error:
            st.error(f"Could not load district coordinates: {error}")
            return
        map_data = district_summary.merge(
            coordinates[
                ["_location_key", "latitude", "longitude"]
            ].rename(columns={"_location_key": "location_key"}),
            on="location_key",
            how="inner",
        )
        if map_data.empty:
            st.info("No district coordinates match the current agriculture records.")
            return
        map_data["marker_color"] = [[88, 195, 123, 220]] * len(map_data)
        if field_districts != "All districts":
            map_data["marker_color"] = [
                [253, 196, 93, 240] if name == field_districts
                else [88, 195, 123, 180]
                for name in map_data["district"]
            ]

        field_metric_columns = st.columns(3, gap="small")
        field_metric_columns[0].metric(
            "Districts with coordinate matches", f"{len(map_data):,}"
        )
        field_metric_columns[1].metric(
            "Recorded area", format_compact(district_summary["area"].sum()) + " ha"
        )
        field_metric_columns[2].metric(
            "Recorded production",
            format_compact(district_summary["production"].sum()) + " t",
        )
        field_map = pdk.Deck(
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=map_data,
                    get_position="[longitude, latitude]",
                    get_fill_color="marker_color",
                    get_radius=6500,
                    radius_min_pixels=4,
                    radius_max_pixels=14,
                    pickable=True,
                    auto_highlight=True,
                )
            ],
            initial_view_state=pdk.ViewState(
                latitude=float(map_data["latitude"].mean()),
                longitude=float(map_data["longitude"].mean()),
                zoom=5 if field_districts != "All districts" else 4,
                pitch=15,
            ),
            map_style=map_style_for_basemap("Satellite imagery"),
            tooltip={
                "html": (
                    "<b>{district}</b>, {state}<br/>"
                    "Recorded area: {area} ha<br/>"
                    "Production: {production} t<br/>"
                    "Records: {record_count}"
                ),
                "style": {"backgroundColor": "#10231a", "color": "#f0f6ef"},
            },
        )
        monitor_columns = st.columns([1.6, 0.9], gap="medium")
        with monitor_columns[0]:
            st.markdown(
                '<div class="market-card-heading">DISTRICT ACTIVITY MAP</div>',
                unsafe_allow_html=True,
            )
            st.pydeck_chart(field_map, width="stretch", height=490)
            st.caption(
                "District-coordinate markers summarize matched records. Recorded "
                "area and production include all districts in the current filters. "
                "Satellite imagery is a basemap only; it "
                "does not provide crop-health observations. Basemap tiles © Esri, "
                "Maxar, Earthstar Geographics, and the GIS User Community."
            )
        with monitor_columns[1]:
            st.markdown(
                '<div class="market-card-heading">DISTRICT RECORDS</div>',
                unsafe_allow_html=True,
            )
            district_table = district_summary.sort_values(
                "production", ascending=False
            ).rename(
                columns={
                    "state": "State",
                    "district": "District",
                    "area": "Area (ha)",
                    "production": "Production (t)",
                    "record_count": "Records",
                }
            )
            st.dataframe(
                district_table[
                    ["State", "District", "Area (ha)", "Production (t)", "Records"]
                ],
                width="stretch",
                hide_index=True,
            )
            st.markdown(
                '<div class="unavailable-signals"><strong>Not in the source data'
                "</strong><span>Soil moisture · NDVI · crop-stress index · "
                "irrigation status · farm parcel boundaries · genetic traits</span>"
                "</div>",
                unsafe_allow_html=True,
            )


@st.cache_data(show_spinner="Loading spatial analysis results...")
def load_river_coverage(coverage_path: str) -> pd.DataFrame:
    dataframe = pd.read_csv(coverage_path)
    required_columns = [
        "district_id",
        "statename",
        "distname",
        "district_area_sq_km",
        "buffer_covered_area_sq_km",
        "coverage_percentage",
    ]
    missing_columns = [
        column for column in required_columns if column not in dataframe
    ]
    if missing_columns:
        raise ValueError(", ".join(missing_columns))

    dataframe = dataframe[required_columns].copy()
    for column in (
        "district_id",
        "district_area_sq_km",
        "buffer_covered_area_sq_km",
        "coverage_percentage",
    ):
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
    for column in ("statename", "distname"):
        dataframe[column] = dataframe[column].astype("string").str.strip()
        dataframe[column] = dataframe[column].replace("", pd.NA)
    return dataframe


def district_id_key(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value).strip()


def spatial_location_key(state: object, district: object) -> str:
    return (
        f"{normalize_state_name(state)}|"
        f"{normalize_location_name(district)}"
    )


@st.cache_data(show_spinner="Preparing interactive district boundaries...")
def load_district_boundaries(boundary_path: str) -> dict:
    with Path(boundary_path).open(encoding="utf-8") as boundary_file:
        boundary_data = json.load(boundary_file)

    simplified_features = []
    for feature in boundary_data.get("features", []):
        geometry = shape(feature["geometry"]).simplify(
            0.01, preserve_topology=True
        )
        simplified_features.append(
            {
                **feature,
                "geometry": mapping(geometry),
                "properties": dict(feature.get("properties", {})),
            }
        )
    return {**boundary_data, "features": simplified_features}


def reset_spatial_map() -> None:
    st.session_state["spatial_map_epoch"] = (
        st.session_state.get("spatial_map_epoch", 0) + 1
    )


def selected_map_feature(selection_state: object) -> dict | None:
    if not isinstance(selection_state, dict):
        return None
    selection = selection_state.get("selection", selection_state)
    if not isinstance(selection, dict):
        return None
    objects = selection.get("objects", {})
    if not isinstance(objects, dict):
        return None
    for selected_features in objects.values():
        if isinstance(selected_features, list) and selected_features:
            selected = selected_features[0]
            if isinstance(selected, dict):
                return selected.get("properties", selected)
    return None


def map_style_for_basemap(selected_basemap: str) -> str:
    if selected_basemap == "Dark geography":
        return "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    satellite_style = {
        "version": 8,
        "sources": {
            "esri-world-imagery": {
                "type": "raster",
                "tiles": [
                    "https://server.arcgisonline.com/ArcGIS/rest/services/"
                    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                ],
                "tileSize": 256,
                "attribution": (
                    "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, "
                    "and the GIS User Community"
                ),
            }
        },
        "layers": [
            {
                "id": "esri-world-imagery",
                "type": "raster",
                "source": "esri-world-imagery",
                "minzoom": 0,
                "maxzoom": 19,
            }
        ],
    }
    return "data:application/json;base64," + base64.b64encode(
        json.dumps(satellite_style).encode("utf-8")
    ).decode("ascii")


def render_spatial_analysis(dataframe: pd.DataFrame) -> None:
    st.markdown(
        '<div class="gis-toolbar">'
        '<div><div class="gis-eyebrow">GEOSPATIAL INTELLIGENCE</div>'
        '<h1 class="gis-title">India field atlas</h1>'
        '<p class="gis-description">Explore mapped district boundaries, '
        "river-buffer exposure, and agricultural records.</p></div>"
        '<div class="gis-toolbar-badge"><span></span> GIS WORKSPACE</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    coverage_path = PROJECT_ROOT / "output" / "river_buffer_coverage_by_district.csv"
    if not coverage_path.is_file():
        st.info(
            "River-buffer results are not available yet. Generate "
            "`output/river_buffer_coverage_by_district.csv` by running "
            "`python 06_buffer_coverage.py` after setting up the PostGIS tables."
        )
        return

    try:
        coverage = load_river_coverage(str(coverage_path))
    except (
        OSError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeDecodeError,
    ) as error:
        st.error(f"Could not load river-buffer results: {error}")
        return
    except ValueError as error:
        st.error(f"River-buffer results are missing required columns: {error}")
        return

    if coverage.empty:
        st.info("The river-buffer results file contains no district records.")
        return

    boundary_path = PROJECT_ROOT / "output" / "districts_intersecting_rivers.geojson"
    if not boundary_path.is_file():
        st.info(
            "District boundary geometry is not available. Add "
            "`output/districts_intersecting_rivers.geojson` to enable the map; "
            "the tabular GIS results below remain available."
        )
        return

    try:
        boundary_data = load_district_boundaries(str(boundary_path))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        st.error(f"Could not load district boundary geometries: {error}")
        return

    all_features = boundary_data.get("features", [])
    if not all_features:
        st.info("No district boundaries are available in the GeoJSON file.")
        return

    epoch = st.session_state.setdefault("spatial_map_epoch", 0)
    map_key = f"gis_map_{epoch}"
    clicked_feature = selected_map_feature(st.session_state.get(map_key))

    state_options = sorted(
        {
            str(feature["properties"].get("statename"))
            for feature in all_features
            if feature.get("properties", {}).get("statename")
        }
    )
    filter_columns = st.columns([1.2, 1.4, 1.15, 1, 0.8, 1.3], gap="small")
    with filter_columns[0]:
        selected_state = st.selectbox(
            "State / territory",
            ["All"] + state_options,
            key="spatial_state",
            on_change=reset_spatial_map,
        )

    available_features = [
        feature
        for feature in all_features
        if selected_state == "All"
        or feature["properties"].get("statename") == selected_state
    ]
    district_rows = sorted(
        {
            (
                str(feature["properties"].get("statename", "")),
                str(feature["properties"].get("distname", "")),
            )
            for feature in available_features
        }
    )
    district_options = [
        f"{state} | {district}" for state, district in district_rows
    ]
    with filter_columns[1]:
        selected_district = st.selectbox(
            "District",
            ["All"] + district_options,
            key="spatial_district",
            on_change=reset_spatial_map,
        )

    with filter_columns[2]:
        crop_options = available_options(dataframe, "crop")
        selected_crop = st.selectbox(
            "Crop",
            ["All"] + crop_options,
            key="spatial_crop",
            on_change=reset_spatial_map,
        )
    with filter_columns[3]:
        season_options = available_options(dataframe, "season")
        selected_season = st.selectbox(
            "Season",
            ["All"] + season_options,
            key="spatial_season",
            on_change=reset_spatial_map,
        )
    with filter_columns[4]:
        year_options = ordered_years(dataframe["year"])
        selected_year = st.selectbox(
            "Year",
            ["All"] + year_options,
            key="spatial_year",
            on_change=reset_spatial_map,
        )
    with filter_columns[5]:
        selected_basemap = st.selectbox(
            "Basemap",
            ["Satellite imagery", "Dark geography"],
            key="spatial_basemap",
            on_change=reset_spatial_map,
        )

    display_columns = st.columns([1.2, 1.4, 1.15, 1.2, 1.05, 0.8], gap="small")
    with display_columns[0]:
        thematic_layer = st.selectbox(
            "Thematic layer",
            [
                "River-buffer coverage",
                "Cultivated area",
                "Production",
                "Average yield",
            ],
            key="spatial_layer",
            on_change=reset_spatial_map,
        )
    with display_columns[1]:
        show_thematic_fill = st.checkbox(
            "Show thematic fill", value=True, key="spatial_show_fill"
        )
    with display_columns[2]:
        show_boundaries = st.checkbox(
            "District outlines", value=True, key="spatial_show_boundaries"
        )
    with display_columns[3]:
        st.caption("Drag to pan · scroll or pinch to zoom · click a district")
    with display_columns[5]:
        st.button(
            "Reset view",
            key="spatial_reset_view",
            on_click=reset_spatial_map,
            width="stretch",
        )

    filtered_agriculture = dataframe.copy()
    if selected_crop != "All":
        filtered_agriculture = filtered_agriculture.loc[
            filtered_agriculture["crop"] == selected_crop
        ]
    if selected_season != "All":
        filtered_agriculture = filtered_agriculture.loc[
            filtered_agriculture["season"] == selected_season
        ]
    if selected_year != "All":
        filtered_agriculture = filtered_agriculture.loc[
            filtered_agriculture["year"] == selected_year
        ]

    filtered_agriculture["_location_key"] = [
        spatial_location_key(state, district)
        for state, district in zip(
            filtered_agriculture["state"], filtered_agriculture["district"]
        )
    ]
    filtered_agriculture["_yield_area"] = filtered_agriculture["area"].where(
        filtered_agriculture["yield"].notna() & filtered_agriculture["area"].gt(0),
        0,
    )
    filtered_agriculture["_weighted_yield"] = (
        filtered_agriculture["_yield_area"] * filtered_agriculture["yield"]
    )
    agriculture_summary = (
        filtered_agriculture.groupby("_location_key", as_index=False)
        .agg(
            cultivated_area=("area", "sum"),
            production=("production", "sum"),
            record_count=("crop", "size"),
            weighted_yield_total=("_weighted_yield", "sum"),
            weighted_yield_area=("_yield_area", "sum"),
        )
    )
    if not agriculture_summary.empty:
        agriculture_summary["average_yield"] = (
            agriculture_summary["weighted_yield_total"]
            / agriculture_summary["weighted_yield_area"].replace(0, np.nan)
        )
    agriculture_by_location = agriculture_summary.set_index(
        "_location_key"
    ).to_dict(orient="index")
    coverage_by_id = {
        district_id_key(row.district_id): row
        for row in coverage.dropna(subset=["district_id"]).itertuples()
    }

    district_pair = (
        selected_district.split(" | ", maxsplit=1)
        if selected_district != "All"
        else None
    )
    active_features = []
    for feature in all_features:
        properties = feature.get("properties", {})
        state = properties.get("statename", "")
        district = properties.get("distname", "")
        if selected_state != "All" and state != selected_state:
            continue
        if district_pair and (state, district) != tuple(district_pair):
            continue

        location_key = spatial_location_key(state, district)
        agricultural_values = agriculture_by_location.get(location_key, {})
        coverage_row = coverage_by_id.get(
            district_id_key(properties.get("district_id"))
        )
        cultivated_area = agricultural_values.get("cultivated_area")
        production_value = agricultural_values.get("production")
        average_yield_value = agricultural_values.get("average_yield")
        coverage_percentage = (
            None
            if coverage_row is None or pd.isna(coverage_row.coverage_percentage)
            else float(coverage_row.coverage_percentage)
        )
        feature_properties = {
            **properties,
            "coverage_percentage": coverage_percentage,
            "district_area_sq_km": (
                None
                if coverage_row is None
                else float(coverage_row.district_area_sq_km)
            ),
            "buffer_covered_area_sq_km": (
                None
                if coverage_row is None
                else float(coverage_row.buffer_covered_area_sq_km)
            ),
            "cultivated_area": (
                None if pd.isna(cultivated_area) else float(cultivated_area)
            ),
            "production": (
                None if pd.isna(production_value) else float(production_value)
            ),
            "average_yield": (
                None if pd.isna(average_yield_value) else float(average_yield_value)
            ),
            "record_count": int(agricultural_values.get("record_count", 0)),
        }
        active_features.append(
            {**feature, "properties": feature_properties}
        )

    metric_fields = {
        "River-buffer coverage": "coverage_percentage",
        "Cultivated area": "cultivated_area",
        "Production": "production",
        "Average yield": "average_yield",
    }
    metric_units = {
        "River-buffer coverage": "%",
        "Cultivated area": "ha",
        "Production": "tonnes",
        "Average yield": "t/ha",
    }
    metric_labels = {
        "River-buffer coverage": "River-buffer area coverage",
        "Cultivated area": "Cultivated area",
        "Production": "Recorded production",
        "Average yield": "Area-weighted yield",
    }
    metric_field = metric_fields[thematic_layer]
    metric_values = [
        feature["properties"].get(metric_field)
        for feature in active_features
        if feature["properties"].get(metric_field) is not None
        and pd.notna(feature["properties"].get(metric_field))
    ]
    thresholds = (
        pd.Series(metric_values, dtype="float64")
        .quantile([0.2, 0.4, 0.6, 0.8])
        .tolist()
        if metric_values
        else []
    )
    color_ramp = [
        [39, 75, 48, 210],
        [50, 103, 63, 220],
        [74, 137, 78, 225],
        [123, 171, 105, 230],
        [187, 207, 143, 235],
    ]

    for feature in active_features:
        properties = feature["properties"]
        value = properties.get(metric_field)
        if not show_thematic_fill:
            fill_color = [0, 0, 0, 0]
        elif value is None or pd.isna(value):
            fill_color = [91, 101, 89, 165]
        else:
            fill_color = color_ramp[
                sum(float(value) > threshold for threshold in thresholds)
            ]
        properties["fill_color"] = fill_color
        properties["line_color"] = (
            [230, 246, 219, 255]
            if clicked_feature
            and district_id_key(clicked_feature.get("district_id"))
            == district_id_key(properties.get("district_id"))
            else [178, 202, 179, 175]
        )

    if selected_district != "All" and active_features:
        selected_geometry = shape(active_features[0]["geometry"])
        center = selected_geometry.representative_point()
        latitude, longitude, zoom = center.y, center.x, 7
    elif selected_state != "All" and active_features:
        bounds = [shape(feature["geometry"]).bounds for feature in active_features]
        longitude = (min(item[0] for item in bounds) + max(item[2] for item in bounds)) / 2
        latitude = (min(item[1] for item in bounds) + max(item[3] for item in bounds)) / 2
        zoom = 5
    else:
        latitude, longitude, zoom = 22.9, 78.9, 3.55

    map_style = map_style_for_basemap(selected_basemap)

    if not active_features:
        st.info("No mapped districts match these filters.")
        return

    main_columns = st.columns([2.25, 0.9], gap="medium")
    with main_columns[0]:
        layer = pdk.Layer(
            "GeoJsonLayer",
            id="district-boundaries",
            data={"type": "FeatureCollection", "features": active_features},
            pickable=True,
            stroked=show_boundaries,
            filled=True,
            get_fill_color="properties.fill_color",
            get_line_color="properties.line_color",
            get_line_width=1,
            line_width_min_pixels=1,
            auto_highlight=True,
            highlight_color=[222, 242, 196, 240],
        )
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=latitude,
                longitude=longitude,
                zoom=zoom,
                pitch=0,
                bearing=0,
            ),
            map_style=map_style,
            map_provider="maplibre" if selected_basemap == "Satellite imagery" else "carto",
            tooltip={
                "html": (
                    "<b>{distname}</b> · {statename}"
                    "<br/>River-buffer coverage: {coverage_percentage}%"
                    "<br/>Agricultural area: {cultivated_area} ha"
                    "<br/>Production: {production} tonnes"
                    "<br/>Yield: {average_yield} t/ha"
                    "<br/>Matching records: {record_count}"
                ),
                "style": {
                    "backgroundColor": "#101a15",
                    "color": "#e8f0e9",
                    "border": "1px solid #3f5947",
                },
            },
        )
        selected_map = st.pydeck_chart(
            deck,
            width="stretch",
            height=650,
            on_select="rerun",
            selection_mode="single-object",
            key=map_key,
        )
        st.markdown(
            '<div class="map-meta-row">'
            '<div class="map-legend">'
            '<span class="legend-title">'
            f"{escape(metric_labels[thematic_layer])} · "
            f"{escape(metric_units[thematic_layer])}</span>"
            '<i class="legend-swatch legend-low"></i><span>Lower</span>'
            '<i class="legend-gradient"></i><span>Higher</span>'
            '<i class="legend-swatch legend-empty"></i><span>No data</span>'
            "</div>"
            '<span class="map-attribution">'
            "Esri satellite imagery; available source polygons: "
            f"{len(all_features):,} districts · 36 states / UTs</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Satellite tiles are a basemap, not live satellite monitoring. "
            "District polygons come from the project's PostGIS export."
        )

    selected_properties = selected_map_feature(
        {
            "selection": (
                selected_map.selection
                if hasattr(selected_map, "selection")
                else {}
            )
        }
    )
    if selected_properties:
        clicked_feature = selected_properties

    selected_geography = clicked_feature
    if selected_geography is None and selected_district != "All":
        state_name, district_name = selected_district.split(" | ", maxsplit=1)
        selected_geography = {
            "statename": state_name,
            "distname": district_name,
        }
    if selected_geography is None and selected_state != "All":
        selected_geography = {"statename": selected_state}

    with main_columns[1]:
        with st.container(key="gis-inspector", border=True):
            st.markdown(
                '<div class="panel-kicker">FEATURE INSPECTOR</div>'
                '<div class="panel-title">Selected geography</div>',
                unsafe_allow_html=True,
            )
            if selected_geography:
                state_name = selected_geography.get("statename", "")
                district_name = selected_geography.get("distname")
                st.markdown(
                    f'<div class="selected-place">{escape(district_name or state_name)}</div>'
                    f'<div class="selected-parent">{escape(state_name)}</div>',
                    unsafe_allow_html=True,
                )
                location_key = (
                    spatial_location_key(state_name, district_name)
                    if district_name
                    else None
                )
                agriculture_values = (
                    agriculture_by_location.get(location_key, {})
                    if location_key
                    else {}
                )
                selected_coverage = next(
                    (
                        row
                        for row in coverage.itertuples()
                        if row.statename == state_name
                        and row.distname == district_name
                    ),
                    None,
                )
                st.markdown(
                    '<div class="panel-divider"></div>', unsafe_allow_html=True
                )
                if district_name:
                    st.metric(
                        "Cultivated area",
                        "—"
                        if pd.isna(agriculture_values.get("cultivated_area", np.nan))
                        else f"{agriculture_values['cultivated_area']:,.0f} ha",
                    )
                    st.metric(
                        "Recorded production",
                        "—"
                        if pd.isna(agriculture_values.get("production", np.nan))
                        else f"{agriculture_values['production']:,.0f} t",
                    )
                    yield_value = agriculture_values.get("average_yield", np.nan)
                    st.metric(
                        "Area-weighted yield",
                        "—" if pd.isna(yield_value) else f"{yield_value:,.2f} t/ha",
                    )
                    if selected_coverage is not None:
                        st.metric(
                            "Within 5 km river buffers",
                            f"{selected_coverage.coverage_percentage:,.1f}%",
                        )
                        st.caption(
                            f"{selected_coverage.buffer_covered_area_sq_km:,.1f} km² "
                            "of district area"
                        )
                    st.caption(
                        f"{agriculture_values.get('record_count', 0):,} matching "
                        "agriculture records"
                    )
                    crop_data = filtered_agriculture.loc[
                        filtered_agriculture["_location_key"] == location_key
                    ]
                    leading_crops = (
                        crop_data.groupby("crop", as_index=False)["production"]
                        .sum(min_count=1)
                        .sort_values("production", ascending=False)
                        .head(5)
                    )
                    if not leading_crops.empty:
                        st.markdown("#### Leading crops")
                        crop_figure = px.bar(
                            leading_crops.sort_values("production"),
                            x="production",
                            y="crop",
                            orientation="h",
                            labels={"production": "Production (tonnes)", "crop": ""},
                            color_discrete_sequence=[ACCENT_GREEN],
                        )
                        chart_layout(crop_figure, height=230)
                        crop_figure.update_layout(margin=dict(l=0, r=0, t=4, b=0))
                        st.plotly_chart(
                            crop_figure,
                            width="stretch",
                            config={"displayModeBar": False},
                        )
                else:
                    state_rows = agriculture_summary.loc[
                        agriculture_summary["_location_key"].str.startswith(
                            normalize_state_name(state_name) + "|"
                        )
                    ]
                    st.metric(
                        "Mapped districts",
                        f"{sum(feature['properties'].get('statename') == state_name for feature in active_features):,}",
                    )
                    st.metric(
                        "Cultivated area",
                        "—"
                        if state_rows.empty
                        else f"{state_rows['cultivated_area'].sum(min_count=1):,.0f} ha",
                    )
                    st.metric(
                        "Recorded production",
                        "—"
                        if state_rows.empty
                        else f"{state_rows['production'].sum(min_count=1):,.0f} t",
                    )
                    st.caption(
                        "Select a district polygon to inspect its crop records and "
                        "river-buffer coverage."
                    )
            else:
                valid_coverage = coverage["coverage_percentage"].dropna()
                national_stats = agriculture_summary
                st.metric("Mapped districts", f"{len(active_features):,}")
                st.metric(
                    "Cultivated area",
                    "—"
                    if national_stats.empty
                    else f"{national_stats['cultivated_area'].sum(min_count=1):,.0f} ha",
                )
                st.metric(
                    "Recorded production",
                    "—"
                    if national_stats.empty
                    else f"{national_stats['production'].sum(min_count=1):,.0f} t",
                )
                st.metric(
                    "Average buffer coverage",
                    "—"
                    if valid_coverage.empty
                    else f"{valid_coverage.mean():.1f}%",
                )
                st.caption(
                    "Select a state or district to focus the map and inspect "
                    "geographic attributes."
                )

    st.subheader("River-buffer coverage by district")
    selected_state = st.session_state.get("spatial_state", selected_state)
    selected_district = st.session_state.get("spatial_district", selected_district)
    filtered_coverage = coverage
    if selected_state != "All":
        filtered_coverage = filtered_coverage.loc[
            filtered_coverage["statename"] == selected_state
        ]
    if selected_district != "All":
        district_state, district_name = selected_district.split(" | ", maxsplit=1)
        filtered_coverage = filtered_coverage.loc[
            (filtered_coverage["statename"] == district_state)
            & (filtered_coverage["distname"] == district_name)
        ]
    valid_coverage = filtered_coverage["coverage_percentage"].dropna()
    if valid_coverage.empty:
        st.info("No valid coverage percentages are available for these filters.")
    else:
        top_districts = (
            filtered_coverage.dropna(subset=["coverage_percentage"])
            .sort_values("coverage_percentage", ascending=False)
            .head(10)
            .sort_values("coverage_percentage")
        )
        coverage_figure = px.bar(
            top_districts,
            x="coverage_percentage",
            y="distname",
            orientation="h",
            labels={
                "coverage_percentage": "District area within 5 km river buffers (%)",
                "distname": "",
            },
            color_discrete_sequence=[ACCENT_GREEN],
            hover_data={
                "statename": True,
                "district_area_sq_km": ":,.2f",
                "buffer_covered_area_sq_km": ":,.2f",
                "coverage_percentage": ":.2f",
            },
        )
        coverage_figure.update_xaxes(range=[0, 100])
        chart_layout(coverage_figure, height=380)
        st.plotly_chart(coverage_figure, width="stretch")

    table_columns = [
        "statename",
        "distname",
        "district_area_sq_km",
        "buffer_covered_area_sq_km",
        "coverage_percentage",
    ]
    st.dataframe(
        filtered_coverage[table_columns]
        .sort_values("coverage_percentage", ascending=False)
        .rename(
            columns={
                "statename": "State / Union territory",
                "distname": "District",
                "district_area_sq_km": "District area (km²)",
                "buffer_covered_area_sq_km": "Area within buffers (km²)",
                "coverage_percentage": "Coverage (%)",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Coverage is the share of each district polygon intersecting the dissolved "
        "5 km river-buffer geometry. Areas were calculated from EPSG:7755 "
        "projected geometries; this is a spatial overlay result, not a measure of "
        "water availability or agricultural impact."
    )

    st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
    st.subheader("District area comparison with Census 2011")
    st.caption(
        "Initial comparison of GIS-derived areas with reference records; district "
        "boundary and area-definition differences remain under investigation. "
        "These national comparison metrics are independent of the filters above."
    )
    comparison_columns = st.columns(4)
    comparison_columns[0].metric("Matched districts", "550")
    comparison_columns[1].metric("Average absolute difference", "206.71 km²")
    comparison_columns[2].metric("Average percentage difference", "6.26%")
    comparison_columns[3].metric("Largest percentage difference", "603.44%")


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


TOOL_GROUPS = {
    "OVERVIEW": ["Dashboard"],
    "CROP INTELLIGENCE": ["What Should I Grow?", "Crop DNA", "Profitability"],
    "MARKET & WEATHER": ["Where Should I Sell?", "Weather Risk"],
    "GEOSPATIAL": ["GIS & Spatial Analysis"],
}
TOOL_ICONS = {
    "Dashboard": ":material/dashboard:",
    "What Should I Grow?": ":material/psychiatry:",
    "Crop DNA": ":material/biotech:",
    "Profitability": ":material/monitoring:",
    "Where Should I Sell?": ":material/storefront:",
    "Weather Risk": ":material/cloud:",
    "GIS & Spatial Analysis": ":material/map:",
}


def select_navigation_group(group: str) -> None:
    selected = st.session_state[f"navigation_{group}"]
    st.session_state["selected_tool"] = selected
    for other_group in TOOL_GROUPS:
        if other_group != group:
            st.session_state[f"navigation_{other_group}"] = None


def clear_dashboard_filters() -> None:
    for key in (
        "dashboard_state",
        "dashboard_district",
        "dashboard_crop",
        "dashboard_season",
        "dashboard_year",
    ):
        st.session_state[key] = "All"


def reset_dependent_filters(changed_filter: str) -> None:
    dependents = {
        "dashboard_state": (
            "dashboard_district",
            "dashboard_crop",
            "dashboard_season",
            "dashboard_year",
        ),
        "dashboard_district": (
            "dashboard_crop",
            "dashboard_season",
            "dashboard_year",
        ),
        "dashboard_crop": ("dashboard_season", "dashboard_year"),
        "dashboard_season": ("dashboard_year",),
    }
    for key in dependents.get(changed_filter, ()):
        st.session_state[key] = "All"


st.session_state.setdefault("selected_tool", "Dashboard")
for group, tools in TOOL_GROUPS.items():
    key = f"navigation_{group}"
    st.session_state.setdefault(
        key,
        st.session_state["selected_tool"]
        if st.session_state["selected_tool"] in tools
        else None,
    )

for key in (
    "dashboard_state",
    "dashboard_district",
    "dashboard_crop",
    "dashboard_season",
    "dashboard_year",
):
    st.session_state.setdefault(key, "All")

with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><div class="brand-mark">🌱</div>'
        '<div><div class="brand-name">Indian Agriculture<br>Statistics</div>'
        '<div class="brand-caption">Agriculture intelligence</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
    for group, tools in TOOL_GROUPS.items():
        st.markdown(
            f'<div class="nav-group-label">{group}</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            group,
            options=tools,
            format_func=lambda tool: f"{TOOL_ICONS[tool]}  {tool}",
            key=f"navigation_{group}",
            index=None,
            label_visibility="collapsed",
            on_change=select_navigation_group,
            args=(group,),
        )

    selected_tool = st.session_state["selected_tool"]
    if selected_tool == "Dashboard":
        st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
        st.markdown("#### Dashboard filters")
        st.caption(
            "Choose a geography and reporting period. Changes update the "
            "dashboard charts and summary."
        )

        state_options = available_options(dataset, "state")
        selected_state = st.selectbox(
            "State",
            ["All"] + state_options,
            key="dashboard_state",
            on_change=reset_dependent_filters,
            args=("dashboard_state",),
        )
        district_source = dataset
        if selected_state != "All":
            district_source = dataset.loc[dataset["state"] == selected_state]
        district_options = available_options(district_source, "district")
        selected_district = st.selectbox(
            "District",
            ["All"] + district_options,
            key="dashboard_district",
            on_change=reset_dependent_filters,
            args=("dashboard_district",),
        )

        crop_source = district_source
        if selected_district != "All":
            crop_source = crop_source.loc[
                crop_source["district"] == selected_district
            ]
        crop_options = available_options(crop_source, "crop")
        selected_crop = st.selectbox(
            "Crop",
            ["All"] + crop_options,
            key="dashboard_crop",
            on_change=reset_dependent_filters,
            args=("dashboard_crop",),
        )

        season_source = crop_source
        if selected_crop != "All":
            season_source = season_source.loc[season_source["crop"] == selected_crop]
        season_options = available_options(season_source, "season")
        selected_season = st.selectbox(
            "Season",
            ["All"] + season_options,
            key="dashboard_season",
            on_change=reset_dependent_filters,
            args=("dashboard_season",),
        )

        year_source = season_source
        if selected_season != "All":
            year_source = year_source.loc[year_source["season"] == selected_season]
        year_options = ordered_years(year_source["year"])
        selected_year = st.selectbox(
            "Year",
            ["All"] + year_options,
            key="dashboard_year",
        )
        st.button(
            "Clear filters",
            type="secondary",
            on_click=clear_dashboard_filters,
            key="clear_dashboard_filters",
        )


if selected_tool != "Dashboard":
    if selected_tool in ("What Should I Grow?", "Crop DNA", "Profitability"):
        reference_file = DATA_DIRECTORY / "crop_economics.csv"
    elif selected_tool == "Where Should I Sell?":
        reference_file = DATA_DIRECTORY / "market_data.csv"
    else:
        reference_file = None

    reference_data = None
    if reference_file is not None:
        if selected_tool == "Crop DNA" and not reference_file.is_file():
            reference_file = None
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
    elif selected_tool == "Crop DNA":
        render_crop_dna(dataset, reference_data)
    elif selected_tool == "Profitability":
        render_profitability(dataset, reference_data)
    elif selected_tool == "Where Should I Sell?":
        render_market_finder(reference_data)
    elif selected_tool == "GIS & Spatial Analysis":
        render_spatial_analysis(dataset)
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

selected_scope = " · ".join(
    value
    for value in (
        selected_state if selected_state != "All" else "",
        selected_district if selected_district != "All" else "",
        selected_crop if selected_crop != "All" else "",
        selected_season if selected_season != "All" else "",
    )
    if value
) or "All India"
reporting_period = selected_year if selected_year != "All" else "All available years"
dashboard_top_crops = (
    filtered_data.dropna(subset=["crop", "area"])
    .groupby("crop", as_index=False)["area"]
    .sum(min_count=1)
    .sort_values("area", ascending=False)
    .head(3)
)
dashboard_crop_area_total = filtered_data["area"].sum(min_count=1)
featured_crop_items = []
for crop_row in dashboard_top_crops.itertuples(index=False):
    share = (
        crop_row.area / dashboard_crop_area_total * 100
        if pd.notna(dashboard_crop_area_total) and dashboard_crop_area_total > 0
        else float("nan")
    )
    share_label = "—" if pd.isna(share) else f"{share:.1f}%"
    featured_crop_items.append(
        '<div class="hero-crop-row"><span>'
        f"{escape(str(crop_row.crop))}</span><strong>"
        f"{format_compact(crop_row.area)} ha</strong><small>"
        f"{share_label}</small></div>"
    )
featured_crops_markup = (
    "".join(featured_crop_items)
    if featured_crop_items
    else '<div class="hero-crop-empty">No crop-area records for these filters.</div>'
)

st.markdown(
    '<section class="dashboard-hero">'
    '<div class="hero-content">'
    '<div class="hero-eyebrow"><span class="hero-live-dot"></span>'
    "AGRICULTURE INTELLIGENCE · INDIA</div>"
    '<div class="hero-main">'
    '<div class="hero-copy">'
    '<div class="hero-greeting">INDIA · AGRICULTURE INTELLIGENCE</div>'
    '<h1>Read the land.<br>Grow with insight.</h1>'
    '<p>Explore crop performance, production patterns, and historical '
    "yield records from across India.</p>"
    "</div>"
    '<div class="hero-context">'
    '<div class="context-label">CURRENT VIEW</div>'
    f'<div class="context-value">{escape(selected_scope)}</div>'
    '<div class="context-divider"></div>'
    '<div class="context-meta">'
    f'<span>REPORTING PERIOD</span><strong>{escape(reporting_period)}</strong>'
    "</div>"
    '<div class="context-meta">'
    f'<span>RECORDS IN VIEW</span><strong>{len(filtered_data):,}</strong>'
    "</div></div>"
    '<div class="hero-crop-panel"><div class="hero-crop-heading">'
    '<span>LEADING CROPS BY AREA</span><span>LIVE VIEW</span></div>'
    f'{featured_crops_markup}'
    '<div class="hero-crop-footnote">Based on recorded cultivated area</div>'
    "</div>"
    "</div>"
    '<div class="hero-footer"><span>District-level crop data</span>'
    '<span class="hero-footer-separator"></span>'
    "<span>Area · Production · Yield</span></div>"
    "</div></section>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-heading">'
    '<div><div class="section-kicker">LIVE SNAPSHOT</div>'
    '<h2 class="section-title">Agricultural overview</h2></div>'
    '<div class="section-note">Based on the active dashboard filters</div>'
    "</div>",
    unsafe_allow_html=True,
)

area_total = filtered_data["area"].sum(min_count=1)
production_total = filtered_data["production"].sum(min_count=1)
yield_data = filtered_data.dropna(subset=["area", "yield"])
yield_data = yield_data.loc[yield_data["area"] > 0]
weighted_area = yield_data["area"].sum(min_count=1)
average_yield = (
    (yield_data["area"] * yield_data["yield"]).sum() / weighted_area
    if pd.notna(weighted_area) and weighted_area > 0
    else float("nan")
)

kpi_columns = st.columns(4)
kpi_columns[0].metric("Total Area · ha", format_compact(area_total))
kpi_columns[1].metric("Total Production · t", format_compact(production_total))
kpi_columns[2].metric(
    "Average Yield · t/ha",
    "—" if pd.isna(average_yield) else f"{average_yield:,.2f} t/ha",
    help=(
        "Calculated as the area-weighted mean of record yields for rows with "
        "valid positive area and yield."
    ),
)
kpi_columns[3].metric("Records in View", f"{len(filtered_data):,}")

if filtered_data.empty:
    st.info("No records match these filters. Adjust one or more selections to continue.")
else:
    state_area = (
        filtered_data.dropna(subset=["state", "area"])
        .groupby("state", as_index=False)["area"]
        .sum(min_count=1)
        .sort_values("area", ascending=False)
        .head(12)
    )
    crop_production = (
        filtered_data.dropna(subset=["crop", "production"])
        .groupby("crop", as_index=False)["production"]
        .sum(min_count=1)
        .sort_values("production", ascending=False)
        .head(12)
    )

    st.markdown(
        '<div class="section-heading chart-section-heading">'
        '<div><div class="section-kicker">REGIONAL PERFORMANCE</div>'
        '<h2 class="section-title">Where the harvest is happening</h2></div>'
        '<div class="section-note">Ranked from the filtered dataset</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    left_chart, right_chart = st.columns([1.05, 0.95], gap="large")
    with left_chart:
        st.subheader("Crop Area by State")
        st.caption("States with the largest recorded crop area.")
        if state_area.empty:
            st.info("No area values are available for the selected records.")
        else:
            state_figure = px.bar(
                state_area,
                x="area",
                y="state",
                orientation="h",
                labels={"area": "Area (hectares)", "state": ""},
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
                height=max(360, min(460, 300 + len(state_area) * 10)),
            )
            st.plotly_chart(state_figure, width="stretch")

    with right_chart:
        st.subheader("Production by Crop")
        st.caption("Crops with the largest recorded production.")
        if crop_production.empty:
            st.info("No production values are available for the selected records.")
        else:
            production_figure = px.bar(
                crop_production,
                x="production",
                y="crop",
                orientation="h",
                labels={"production": "Production (tonnes)", "crop": ""},
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
                height=max(360, min(460, 300 + len(crop_production) * 10)),
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

    state_crop_area = (
        filtered_data.dropna(subset=["state", "crop", "area"])
        .groupby(["state", "crop"])["area"]
        .sum(min_count=1)
        .unstack(fill_value=0)
    )
    if not state_crop_area.empty:
        top_state_names = (
            state_crop_area.sum(axis=1).nlargest(12).index
        )
        top_crop_names = (
            state_crop_area.sum(axis=0).nlargest(10).index
        )
        state_crop_area = state_crop_area.loc[top_state_names, top_crop_names]

    st.markdown(
        '<div class="section-heading chart-section-heading">'
        '<div><div class="section-kicker">TRENDS & MIX</div>'
        '<h2 class="section-title">A longer view of the land</h2></div>'
        '<div class="section-note">Historical area and crop distribution</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    trend_column, mix_column = st.columns([1.08, 0.92], gap="large")
    with trend_column:
        st.subheader("Crop Area by Year")
        st.caption("Annual area totals across the reporting period.")
        if annual_area.empty:
            st.info(
                "No valid year and area values are available for the selected records."
            )
        else:
            annual_figure = px.area(
                annual_area,
                x="year",
                y="area",
                markers=True,
                labels={"year": "Year", "area": "Area (hectares)"},
                color_discrete_sequence=[ACCENT_GREEN],
            )
            annual_figure.update_traces(
                line=dict(width=2.5),
                marker=dict(size=5),
                fillcolor="rgba(126, 170, 135, 0.17)",
                hovertemplate="%{x}<br>Area: %{y:,.2f} ha<extra></extra>",
            )
            chart_layout(annual_figure, height=410)
            annual_figure.update_layout(showlegend=False)
            annual_figure.update_xaxes(showgrid=False, tickangle=-30)
            st.plotly_chart(annual_figure, width="stretch")

    with mix_column:
        st.subheader("State × Crop Area")
        st.caption("Compare where the leading crops are grown.")
        if state_crop_area.empty:
            st.info(
                "No state, crop and area combinations are available for the selection."
            )
        else:
            heatmap_figure = px.imshow(
                state_crop_area,
                labels={"x": "Crop", "y": "State", "color": "Area"},
                aspect="auto",
                color_continuous_scale=[
                    "#1a2a20",
                    "#31543c",
                    "#5f8a63",
                    "#a7c4a0",
                    "#d6e5d4",
                ],
            )
            heatmap_figure.update_traces(
                hovertemplate="State: %{y}<br>Crop: %{x}<br>Area: "
                "%{z:,.2f} ha<extra></extra>"
            )
            heatmap_figure.update_xaxes(tickangle=-35)
            chart_layout(heatmap_figure, height=410)
            heatmap_figure.update_layout(
                showlegend=False,
                coloraxis_colorbar=dict(title="Hectares", thickness=10),
            )
            st.plotly_chart(heatmap_figure, width="stretch")

with st.expander("View filtered records"):
    if filtered_data.empty:
        st.info("No records are available for the current filters.")
    else:
        page_size = 50
        page_count = (len(filtered_data) + page_size - 1) // page_size
        saved_page = st.session_state.get("dashboard_table_page", 1)
        try:
            table_page_value = int(saved_page)
        except (TypeError, ValueError):
            table_page_value = 1
        if not 1 <= table_page_value <= page_count:
            table_page_value = 1
        st.session_state["dashboard_table_page"] = table_page_value
        table_page = st.selectbox(
            "Page",
            range(1, page_count + 1),
            format_func=lambda page: f"{page} of {page_count}",
            key="dashboard_table_page",
        )
        start_row = (table_page - 1) * page_size
        end_row = min(start_row + page_size, len(filtered_data))
        st.caption(
            f"Showing records {start_row + 1:,}–{end_row:,} "
            f"of {len(filtered_data):,}."
        )
        st.dataframe(
            filtered_data.iloc[start_row:end_row],
            width="stretch",
            hide_index=True,
        )
