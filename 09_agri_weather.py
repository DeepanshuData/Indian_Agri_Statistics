import pandas as pd
import requests


df = pd.read_csv("data/agridata.csv")

coordinates = pd.read_csv("data/district_coordinates.csv")


merged_data = pd.merge(
    df,
    coordinates,
    on=["district", "state"],
    how="inner"
)


weather_data = []


for _, row in coordinates.iterrows():

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "current": "temperature_2m,relative_humidity_2m,precipitation"
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:

        data = response.json()

        weather_data.append({
            "district": row["district"],
            "state": row["state"],
            "temperature": data["current"]["temperature_2m"],
            "humidity": data["current"]["relative_humidity_2m"],
            "precipitation": data["current"]["precipitation"]
        })


weather_df = pd.DataFrame(weather_data)


final_data = pd.merge(
    merged_data,
    weather_df,
    on=["district", "state"],
    how="left"
)


print(final_data.head())

final_data.to_csv(
    "output/agriculture_weather.csv",
    index=False
)

print("\nAgriculture + weather data saved successfully.")