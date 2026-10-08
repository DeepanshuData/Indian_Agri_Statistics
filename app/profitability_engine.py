import pandas as pd

if __package__:
    from .recommendation_engine import canonical_crop_name
else:
    from recommendation_engine import canonical_crop_name


def load_crop_economics(file_path="data/crop_economics.csv"):
    return pd.read_csv(file_path)


def calculate_profitability(
    crop,
    land_acres,
    historical_yield,
    economics,
    price_per_kg=None,
    cost_per_acre=None
):
    crop_data = economics[
        economics["crop"].map(canonical_crop_name)
        == canonical_crop_name(crop)
    ]

    if crop_data.empty:
        return None

    crop_data = crop_data.iloc[0]

    cost_per_acre = (
        crop_data["cost_per_acre"]
        if cost_per_acre is None
        else cost_per_acre
    )
    price_per_kg = (
        crop_data["price_per_kg"]
        if price_per_kg is None
        else price_per_kg
    )

    total_cost = cost_per_acre * land_acres

    land_hectares = land_acres * 0.404686

    expected_production_tonnes = (
        historical_yield * land_hectares
    )

    expected_production_kg = (
        expected_production_tonnes * 1000
    )

    expected_revenue = (
        expected_production_kg * price_per_kg
    )

    expected_profit = (
        expected_revenue - total_cost
    )

    if total_cost > 0:
        roi = (
            expected_profit / total_cost
        ) * 100
    else:
        roi = 0

    volatility = crop_data["price_volatility"]

    if volatility >= 0.30:
        risk = "High"
    elif volatility >= 0.18:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        "Crop": crop,
        "Expected Production (tonnes)": round(
            expected_production_tonnes, 2
        ),
        "Expected Revenue": round(
            expected_revenue, 2
        ),
        "Estimated Cost": round(
            total_cost, 2
        ),
        "Expected Profit": round(
            expected_profit, 2
        ),
        "ROI (%)": round(
            roi, 2
        ),
        "Risk": risk,
        "Price Volatility": volatility,
        "Water Requirement": crop_data[
            "water_requirement"
        ]
    }