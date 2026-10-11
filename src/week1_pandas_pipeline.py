
from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from db_connection import load_agriculture_data, engine


# ==================================================
# 1. SET UP PROJECT AND OUTPUT FOLDERS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
CHART_DIR = OUTPUT_DIR / "charts"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR.mkdir(parents=True, exist_ok=True)


try:
    # ==============================================
    # 2. LOAD DATA FROM POSTGRESQL
    # ==============================================

    df = load_agriculture_data()

    print("\n========== DATA LOADING ==========")
    print("Source: PostgreSQL")
    print("Table: public.agriculture")
    print("Dataset shape:", df.shape)
    print(df.head())


    # ==============================================
    # 3. INSPECT THE DATA
    # ==============================================

    print("\n========== DATA INSPECTION ==========")

    print("\nColumn names:")
    print(df.columns.tolist())

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nExact duplicate rows:")
    print(df.duplicated().sum())

    print("\nUnique crops:", df["crop"].nunique())
    print("Unique states:", df["state"].nunique())
    print("Unique districts:", df["district"].nunique())

    print("\nNumerical summary:")
    print(df[["area", "production", "yield"]].describe())


    # ==============================================
    # 4. CLEAN THE DATA
    # ==============================================

    print("\n========== DATA CLEANING ==========")

    clean_df = df.copy()

    original_rows = len(clean_df)

    # Remove exact duplicate records
    clean_df = clean_df.drop_duplicates()

    # Standardize text columns
    text_columns = [
        "state",
        "district",
        "crop",
        "year",
        "season",
    ]

    for column in text_columns:
        clean_df[column] = (
            clean_df[column]
            .astype("string")
            .str.strip()
        )

    # Convert blank strings into missing values
    clean_df[text_columns] = clean_df[text_columns].replace(
        "", pd.NA
    )

    # Convert numerical columns to numeric data types
    numeric_columns = ["area", "production", "yield"]

    for column in numeric_columns:
        clean_df[column] = pd.to_numeric(
            clean_df[column],
            errors="coerce",
        )

    # Remove records missing essential grouping information
    clean_df = clean_df.dropna(
        subset=["state", "district", "crop", "year", "season"]
    )

    clean_df = clean_df.reset_index(drop=True)

    print("Original rows:", original_rows)
    print("Rows after cleaning:", len(clean_df))
    print("Rows removed:", original_rows - len(clean_df))
    print("\nMissing values after cleaning:")
    print(clean_df.isnull().sum())

    # Save cleaned data locally
    clean_df.to_csv(
        OUTPUT_DIR / "cleaned_agriculture_data.csv",
        index=False,
    )


    # ==============================================
    # 5. NUMPY CALCULATIONS
    # ==============================================

    print("\n========== NUMPY ANALYSIS ==========")

    area_array = clean_df["area"].to_numpy(dtype=float)

    print("Area array shape:", area_array.shape)
    print("Total area:", np.nansum(area_array))

    if not np.isnan(area_array).all():
        print("Average area:", np.nanmean(area_array))
    else:
        print("Average area: unavailable")

    # Calculate production per unit area when area is positive
    area_values = clean_df["area"].to_numpy(dtype=float)
    production_values = clean_df["production"].to_numpy(dtype=float)

    production_per_area = np.divide(
        production_values,
        area_values,
        out=np.full(len(clean_df), np.nan),
        where=(
            (area_values > 0)
            & np.isfinite(area_values)
            & np.isfinite(production_values)
        ),
    )

    clean_df["production_per_area"] = production_per_area


    # ==============================================
    # 6. GROUPBY ANALYSIS
    # ==============================================

    print("\n========== GROUPBY ANALYSIS ==========")

    # Summarize production and area for each crop
    crop_summary = (
        clean_df.groupby("crop")
        .agg(
            total_area=("area", "sum"),
            total_production=("production", "sum"),
            average_yield=("yield", "mean"),
            record_count=("crop", "size"),
        )
        .reset_index()
        .sort_values("total_production", ascending=False)
    )

    print("\nTop 10 crops by production:")
    print(crop_summary.head(10).to_string(index=False))

    # Summarize production and area for each state
    state_summary = (
        clean_df.groupby("state")
        .agg(
            total_area=("area", "sum"),
            total_production=("production", "sum"),
            average_yield=("yield", "mean"),
        )
        .reset_index()
    )

    print("\nState summary:")
    print(state_summary.head(10).to_string(index=False))

    crop_summary.to_csv(
        OUTPUT_DIR / "crop_summary.csv",
        index=False,
    )

    state_summary.to_csv(
        OUTPUT_DIR / "state_summary.csv",
        index=False,
    )


    # ==============================================
    # 7. MERGE ANALYSIS
    # ==============================================

    print("\n========== MERGE ANALYSIS ==========")

    # Calculate crop statistics separately for each state
    state_crop_summary = (
        clean_df.groupby(["state", "crop"])
        .agg(
            crop_production=("production", "sum"),
            crop_area=("area", "sum"),
            crop_average_yield=("yield", "mean"),
        )
        .reset_index()
    )

    # Identify the leading crop in each state by production
    leading_crop = (
        state_crop_summary
        .sort_values(
            ["state", "crop_production", "crop"],
            ascending=[True, False, True],
        )
        .drop_duplicates(subset="state")
    )

    # Combine leading-crop statistics with state-level statistics
    merged_summary = leading_crop.merge(
        state_summary,
        on="state",
        how="left",
        suffixes=("_crop", "_state"),
        validate="one_to_one",
    )

    print("\nLeading crop for each state:")
    print(merged_summary.head(10).to_string(index=False))

    merged_summary.to_csv(
        OUTPUT_DIR / "state_leading_crop_summary.csv",
        index=False,
    )


    # ==============================================
    # 8. PIVOT TABLE
    # ==============================================

    print("\n========== PIVOT TABLE ==========")

    # Rows = states, columns = seasons, values = production totals
    pivot_table = pd.pivot_table(
        clean_df,
        index="state",
        columns="season",
        values="production",
        aggfunc="sum",
        fill_value=0,
    )

    print(pivot_table.head(10))

    pivot_table.to_csv(
        OUTPUT_DIR / "state_season_production_pivot.csv"
    )


    # ==============================================
    # 9. VISUALIZATION
    # ==============================================

    print("\n========== VISUALIZATION ==========")

    # Chart 1: Top 10 crops by total production
    top_crops = crop_summary.head(10).sort_values(
        "total_production"
    )

    if not top_crops.empty:
        plt.figure(figsize=(11, 6))

        plt.barh(
            top_crops["crop"].astype(str),
            top_crops["total_production"],
        )

        plt.title("Top 10 Crops by Total Production")
        plt.xlabel("Total Production")
        plt.ylabel("Crop")
        plt.tight_layout()

        plt.savefig(
            CHART_DIR / "top_10_crops_production.png",
            dpi=150,
        )

        plt.close()

    # Chart 2: Top 10 states by total production
    top_states = state_summary.nlargest(
        10, "total_production"
    ).sort_values("total_production")

    if not top_states.empty:
        plt.figure(figsize=(12, 6))

        plt.barh(
            top_states["state"].astype(str),
            top_states["total_production"],
        )

        plt.title("Top 10 States by Total Production")
        plt.xlabel("Total Production")
        plt.ylabel("State")
        plt.tight_layout()

        plt.savefig(
            CHART_DIR / "top_10_states_production.png",
            dpi=150,
        )

        plt.close()

    print("Charts saved in:", CHART_DIR)


    # ==============================================
    # 10. SAVE PIPELINE SUMMARY
    # ==============================================

    summary = {
        "source": "PostgreSQL",
        "database": "agriculture_db",
        "table": "public.agriculture",
        "rows_loaded": int(len(df)),
        "rows_after_cleaning": int(len(clean_df)),
        "rows_removed": int(len(df) - len(clean_df)),
        "columns_loaded": int(df.shape[1]),
        "unique_crops": int(clean_df["crop"].nunique()),
        "unique_states": int(clean_df["state"].nunique()),
        "unique_districts": int(clean_df["district"].nunique()),
    }

    with open(
        OUTPUT_DIR / "pipeline_summary.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(summary, file, indent=4)

    print("\n========== PIPELINE COMPLETED ==========")
    print("Loaded rows:", len(df))
    print("Cleaned rows:", len(clean_df))
    print("Output folder:", OUTPUT_DIR)

finally:
    engine.dispose()
