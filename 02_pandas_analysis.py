from getpass import getpass
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, URL

# 1. Connect to PostgreSQL
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres",
    password=getpass("Enter your PostgreSQL password: "),
    host="localhost",
    port=5432,
    database="agriculture_db"
)

engine = create_engine(connection_url)

try:
    # 2. Query the existing spatial analysis table
    query = """
    SELECT
        district_id,
        statename,
        distname,
        district_area_sq_km
    FROM public.river_buffer_district_analysis
    ORDER BY district_area_sq_km DESC;
    """

    # 3. Load SQL results into Pandas
    df = pd.read_sql_query(query, engine)

    # 4. Inspect the data
    print("\nFirst five rows:")
    print(df.head())

    print("\nDataset shape:")
    print(df.shape)

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isnull().sum())

    # 5. Analyze the districts
    print("\nTop 10 largest districts:")
    print(df.head(10))

    print("\nDistrict count by state:")
    print(df["statename"].value_counts())

    print("\nAverage district area by state:")
    state_summary = (
        df.groupby("statename")["district_area_sq_km"]
        .mean()
        .sort_values(ascending=False)
    )
    print(state_summary)

    # 6. Save results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        output_dir / "river_district_analysis.csv",
        index=False
    )

    state_summary.to_csv(
        output_dir / "average_district_area_by_state.csv",
        header=["average_area_sq_km"]
    )

    print("\nCSV files saved successfully!")

finally:
    engine.dispose()
