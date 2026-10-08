import pandas as pd


def load_market_data(
    file_path="data/market_data.csv"
):
    return pd.read_csv(file_path)


def calculate_market_opportunity(
    market_data,
    crop,
    origin_market,
    quantity_tonnes
):
    data = market_data[
        market_data["crop"].str.lower()
        == crop.lower()
    ].copy()

    data = data[
        data["origin_market"].str.lower()
        == origin_market.lower()
    ]

    if data.empty:
        return pd.DataFrame()

    quantity_kg = quantity_tonnes * 1000

    data["Gross Revenue"] = (
        data["current_price_per_kg"]
        * quantity_kg
    )

    data["Transport Cost"] = (
        data["transport_cost_per_kg"]
        * quantity_kg
    )

    data["Net Realization"] = (
        data["Gross Revenue"]
        - data["Transport Cost"]
    )

    data["Net Price per Kg"] = (
        data["Net Realization"]
        / quantity_kg
    )

    data = data.sort_values(
        "Net Realization",
        ascending=False
    )

    return data
