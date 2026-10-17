import csv
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

import requests


COORDINATES_PATH = (
    Path(__file__).resolve().parents[1] / "Data" / "district_coordinates.csv"
)
STATE_ALIASES = {
    "anislands": "andamannicobarislands",
    "chhattisgarh": "chhatisgarh",
    "delhi": "nctofdelhi",
    "dnhaveli": "dadranagarhaveli",
    "meghalya": "meghalaya",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
}


def normalize_location_name(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", normalized.casefold())


def normalize_state_name(state):
    normalized = normalize_location_name(state)
    return STATE_ALIASES.get(normalized, normalized)


@lru_cache(maxsize=1)
def load_coordinate_indexes():
    district_coordinates = {}
    state_coordinates = {}

    with COORDINATES_PATH.open(encoding="utf-8", newline="") as coordinates_file:
        for row in csv.DictReader(coordinates_file):
            state = normalize_state_name(row["state"])
            district = normalize_location_name(row["district"])
            location = {
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
            }
            if district:
                district_coordinates[(state, district)] = location
            elif row.get("precision") == "state":
                state_coordinates[state] = location

    return district_coordinates, state_coordinates


def local_location(district, state):
    district_coordinates, state_coordinates = load_coordinate_indexes()
    state_key = normalize_state_name(state)
    district_key = normalize_location_name(district)

    location = district_coordinates.get((state_key, district_key))
    if location is not None:
        return {
            **location,
            "name": f"{district.title()}, {state.title()}",
            "precision": "district",
        }

    return None


def geocode_location(
    district,
    state
):
    location = local_location(district, state)
    if location is not None:
        return location

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": district,
        "count": 100,
        "language": "en",
        "format": "json"
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    results = data.get("results") or []
    if not results:
        results = []

    state_key = normalize_state_name(state)
    district_key = normalize_location_name(district)
    for result in results:
        if normalize_location_name(result.get("country", "")) != "india":
            continue
        if normalize_location_name(result.get("name", "")) != district_key:
            continue
        result_state = result.get("admin1")
        if result_state and normalize_state_name(result_state) != state_key:
            continue
        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "name": result["name"],
            "precision": "district",
        }

    _, state_coordinates = load_coordinate_indexes()
    fallback = state_coordinates.get(state_key)
    if fallback is None:
        return None

    return {
        **fallback,
        "name": f"{state.title()} (approximate state-level location)",
        "precision": "state",
    }


def get_weather_forecast(
    latitude,
    longitude
):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max"
        ],
        "forecast_days": 5,
        "timezone": "auto"
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


def calculate_weather_risk(
    forecast
):
    daily = forecast.get("daily")
    if not daily:
        raise ValueError("The weather response does not contain daily forecasts.")

    rainfall_values = daily.get("precipitation_sum") or []
    probability_values = daily.get("precipitation_probability_max") or []
    if not rainfall_values or not probability_values:
        raise ValueError("The weather response is missing rainfall or probability data.")

    total_rainfall = sum(
        value or 0
        for value in rainfall_values
    )

    max_rain_probability = max(
        (value or 0 for value in probability_values)
    )

    if (
        total_rainfall >= 100
        or max_rain_probability >= 80
    ):
        risk = "High"

    elif (
        total_rainfall >= 50
        or max_rain_probability >= 60
    ):
        risk = "Medium"

    else:
        risk = "Low"

    return {
        "Risk": risk,
        "Total 5-Day Rainfall": round(
            total_rainfall,
            1
        ),
        "Maximum Rain Probability": max_rain_probability
    }
    