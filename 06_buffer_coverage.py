from getpass import getpass
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, URL

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
    query = """
    WITH buffer_union AS (
        SELECT ST_UnaryUnion(ST_Collect(geom)) AS geom
        FROM public.river_buffer_5km
    ),
    district_coverage AS (
        SELECT
            d.gid AS district_id,
            d.statename,
            d.distname,
            ST_Area(d.geom) / 1000000.0
                AS district_area_sq_km,
            ST_Area(
                ST_Intersection(d.geom, b.geom)
            ) / 1000000.0
                AS buffer_covered_area_sq_km
        FROM public.indian_districts_7755 AS d
        CROSS JOIN buffer_union AS b
        WHERE ST_Intersects(d.geom, b.geom)
    )
    SELECT
        district_id,
        statename,
        distname,
        ROUND(district_area_sq_km::numeric, 2)
            AS district_area_sq_km,
        ROUND(buffer_covered_area_sq_km::numeric, 2)
            AS buffer_covered_area_sq_km,
        ROUND(
            (
                buffer_covered_area_sq_km
                / NULLIF(district_area_sq_km, 0)
            )::numeric * 100,
            2
        ) AS coverage_percentage
    FROM district_coverage
    ORDER BY coverage_percentage DESC;
    """

    # Load attribute-only SQL results into Pandas
    df = pd.read_sql_query(query, engine)

    print("\nFirst 10 districts by coverage:")
    print(df.head(10).to_string(index=False))

    print("\nDataset shape:")
    print(df.shape)

    print("\nTotal districts analyzed:", len(df))

    print("\nAverage district coverage:")
    print(round(df["coverage_percentage"].mean(), 2), "%")

    print("\nTop 10 districts by coverage:")
    print(
        df[
            ["statename", "distname", "coverage_percentage"]
        ].head(10).to_string(index=False)
    )

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        output_dir / "river_buffer_coverage_by_district.csv",
        index=False
    )

    print("\nCoverage results saved successfully!")

finally:
    engine.dispose()
