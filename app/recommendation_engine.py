import numpy as np
import pandas as pd


def canonical_crop_name(crop):
    """Normalize common differences between statistics and reference crop names."""
    normalized = str(crop).strip().lower()
    aliases = {
        "soyabean": "soybean",
        "cotton(lint)": "cotton",
    }
    return aliases.get(normalized, normalized)


def get_historical_crop_summary(df, state, district, season=None):
    """Aggregate valid district-season production and area before calculating yield."""
    data = df.loc[
        df["state"].astype("string").str.strip().str.casefold().eq(
            str(state).strip().casefold()
        )
        & df["district"].astype("string").str.strip().str.casefold().eq(
            str(district).strip().casefold()
        )
    ].copy()
    if season and season != "All":
        data = data.loc[
            data["season"].astype("string").str.strip().str.casefold().eq(
                str(season).strip().casefold()
            )
        ]

    data["crop"] = data["crop"].astype("string").str.strip()
    data["year"] = data["year"].astype("string").str.strip()
    data["area"] = pd.to_numeric(data["area"], errors="coerce")
    data["production"] = pd.to_numeric(data["production"], errors="coerce")
    valid_year = data["year"].str.fullmatch(r"\d{4}(?:-\d{2}|\d{4})?").fillna(False)
    valid_values = (
        np.isfinite(data["area"])
        & np.isfinite(data["production"])
        & data["area"].gt(0)
        & data["production"].ge(0)
        & data["crop"].notna()
        & data["crop"].ne("")
        & valid_year
    )
    valid = data.loc[valid_values]
    if valid.empty:
        return pd.DataFrame(
            columns=[
                "crop",
                "total_area",
                "total_production",
                "observations",
                "years_of_history",
                "historical_yield",
            ]
        )

    summary = (
        valid.groupby("crop", as_index=False)
        .agg(
            total_area=("area", "sum"),
            total_production=("production", "sum"),
            observations=("crop", "size"),
            years_of_history=("year", "nunique"),
        )
    )
    summary["historical_yield"] = (
        summary["total_production"] / summary["total_area"]
    )
    return summary.sort_values(
        ["historical_yield", "crop"], ascending=[False, True]
    ).reset_index(drop=True)


def calculate_risk(
    price_volatility,
    water_requirement,
    irrigation,
    weather_risk=None,
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
