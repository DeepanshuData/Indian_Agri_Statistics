import pandas as pd


def canonical_crop_name(crop):
    """Normalize common differences between statistics and reference crop names."""
    normalized = str(crop).strip().lower()
    aliases = {
        "soyabean": "soybean",
        "cotton(lint)": "cotton",
    }
    return aliases.get(normalized, normalized)


def get_historical_crop_yields(
    df,
    district,
    season=None
):
    data = df[
        df["district"].str.lower()
        == district.lower()
    ].copy()

    if season and season != "All":
        data = data[
            data["season"].str.lower()
            == season.lower()
        ]

    result = (
        data.groupby("crop")["yield"]
        .mean()
        .reset_index()
    )

    result.columns = [
        "crop",
        "historical_yield"
    ]

    return result


def calculate_risk(
    price_volatility,
    water_requirement,
    irrigation,
    weather_risk=None
):
    score = 0

    if price_volatility >= 0.30:
        score += 3
    elif price_volatility >= 0.18:
        score += 2
    else:
        score += 1

    if water_requirement == "High":
        if irrigation == "No":
            score += 3
        elif irrigation == "Partial":
            score += 2

    elif water_requirement == "Medium":
        if irrigation == "No":
            score += 2
        elif irrigation == "Partial":
            score += 1

    if weather_risk == "High":
        score += 2
    elif weather_risk == "Medium":
        score += 1

    if score >= 5:
        return "High"

    if score >= 3:
        return "Medium"

    return "Low"


def recommend_crops(
    df,
    economics,
    district,
    land_acres,
    budget,
    irrigation,
    season,
    weather_risk=None
):
    yields = get_historical_crop_yields(
        df,
        district,
        season
    )

    recommendations = []

    for _, row in yields.iterrows():

        crop = row["crop"]
        historical_yield = row["historical_yield"]

        if pd.isna(historical_yield):
            continue

        economic_result = economics[
            economics["crop"].map(canonical_crop_name)
            == canonical_crop_name(crop)
        ]

        if economic_result.empty:
            continue

        economic_result = economic_result.iloc[0]

        cost_per_acre = economic_result[
            "cost_per_acre"
        ]

        total_cost = (
            cost_per_acre * land_acres
        )

        if total_cost > budget:
            continue

        price_volatility = economic_result[
            "price_volatility"
        ]

        water_requirement = economic_result[
            "water_requirement"
        ]

        risk = calculate_risk(
            price_volatility,
            water_requirement,
            irrigation,
            weather_risk
        )

        land_hectares = land_acres * 0.404686

        production = (
            historical_yield
            * land_hectares
        )

        revenue = (
            production
            * 1000
            * economic_result["price_per_kg"]
        )

        profit = revenue - total_cost

        roi = (
            profit / total_cost * 100
            if total_cost > 0
            else 0
        )

        score = roi

        if risk == "Low":
            score += 15
        elif risk == "Medium":
            score += 5
        else:
            score -= 10

        if weather_risk == "Medium":
            score -= 5
        elif weather_risk == "High":
            score -= 15

        recommendation = {
            "Crop": crop,
            "Historical Yield": round(
                historical_yield, 2
            ),
            "Expected Revenue": round(
                revenue, 2
            ),
            "Estimated Cost": round(
                total_cost, 2
            ),
            "Expected Profit": round(
                profit, 2
            ),
            "ROI (%)": round(
                roi, 2
            ),
            "Risk": risk,
            "Score": round(score, 2)
        }
        if weather_risk is not None:
            recommendation["Weather Risk"] = weather_risk
        recommendations.append(recommendation)

    result = pd.DataFrame(
        recommendations
    )

    if result.empty:
        return result

    return result.sort_values(
        "Score",
        ascending=False
    ).reset_index(drop=True)
    