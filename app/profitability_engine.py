import math

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
    expected_production_kg,
    economics,
    price_per_kg=None,
    cost_per_acre=None,
):
    """Estimate returns from a user-entered harvest amount, without yield conversion."""
    crop_data = economics.loc[
        economics["crop"].map(canonical_crop_name)
        == canonical_crop_name(crop)
    ]
    if crop_data.empty:
        return None

    crop_data = crop_data.iloc[0]
    cost_per_acre = (
        crop_data["cost_per_acre"] if cost_per_acre is None else cost_per_acre
    )
    price_per_kg = (
        crop_data["price_per_kg"] if price_per_kg is None else price_per_kg
    )

    inputs = {
        "land area": land_acres,
        "expected production": expected_production_kg,
        "selling price": price_per_kg,
        "cost per acre": cost_per_acre,
        "price volatility": crop_data["price_volatility"],
    }
    numeric_inputs = {}
    for label, value in inputs.items():
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label.title()} must be a number.") from error
        if not math.isfinite(numeric_value) or numeric_value < 0:
            raise ValueError(f"{label.title()} must be finite and non-negative.")
        numeric_inputs[label] = numeric_value
    if numeric_inputs["land area"] == 0:
        raise ValueError("Land area must be greater than zero.")

    total_cost = numeric_inputs["cost per acre"] * numeric_inputs["land area"]
    expected_revenue = (
        numeric_inputs["expected production"] * numeric_inputs["selling price"]
    )
    expected_profit = expected_revenue - total_cost
    roi = expected_profit / total_cost * 100 if total_cost > 0 else 0
    volatility = numeric_inputs["price volatility"]

    if volatility >= 0.30:
        risk = "High"
    elif volatility >= 0.18:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        "Crop": crop,
        "Expected Production (kg)": round(numeric_inputs["expected production"], 2),
        "Expected Revenue": round(expected_revenue, 2),
        "Estimated Cost": round(total_cost, 2),
        "Expected Profit": round(expected_profit, 2),
        "ROI (%)": round(roi, 2),
        "Risk": risk,
        "Price Volatility": volatility,
        "Water Requirement": crop_data["water_requirement"],
    }
