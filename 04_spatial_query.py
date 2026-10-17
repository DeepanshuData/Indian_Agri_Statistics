from getpass import getpass
from pathlib import Path

import geopandas as gpd
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
    # Find districts that intersect river buffer polygons
    query = """
    SELECT
        d.gid AS district_id,
        d.statename,
        d.distname,
        d.geom
    FROM public.indian_districts_7755 AS d
    WHERE EXISTS (
        SELECT 1
        FROM public.river_buffer_5km AS b
        WHERE ST_Intersects(d.geom, b.geom)
    )
    ORDER BY d.statename, d.distname;
    """

    # Load the query results into a GeoDataFrame
    gdf = gpd.read_postgis(
        query,
        engine,
        geom_col="geom"
    )

    print("\nFirst five matching districts:")
    print(gdf.head())

    print("\nDataset shape:")
    print(gdf.shape)

    print("\nNumber of matching districts:")
    print(len(gdf))

    print("\nMatching districts by state:")
    print(gdf["statename"].value_counts())

    # Save results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    gdf.drop(columns="geom").to_csv(
        output_dir / "districts_intersecting_rivers.csv",
        index=False
    )

    gdf.to_crs(epsg=4326).to_file(
        output_dir / "districts_intersecting_rivers.geojson",
        driver="GeoJSON"
    )

    print("\nCSV and GeoJSON files saved successfully!")

finally:
    engine.dispose()
