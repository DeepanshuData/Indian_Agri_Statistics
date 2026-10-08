import requests


def geocode_location(
    district,
    state
):
    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": f"{district}, {state}, India",
        "count": 1,
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
        return None

    result = results[0]

    return {
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "name": result["name"]
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
    