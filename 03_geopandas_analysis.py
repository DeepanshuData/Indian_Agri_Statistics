from getpass import getpass
from pathlib import Path

import geopandas as gpd
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
    # 2. Select district attributes, area and geometry
    query = """
    SELECT
        d.gid AS district_id,
        d.statename,
        d.distname,
        a.district_area_sq_km,
        d.geom
    FROM public.indian_districts_7755 AS d
    JOIN public.river_buffer_district_analysis AS a
        ON d.gid = a.district_id;
    """

    # 3. Load SQL results into a GeoDataFrame
    gdf = gpd.read_postgis(
        query,
        engine,
        geom_col="geom"
    )

    # 4. Inspect the spatial data
    print("\nFirst five rows:")
    print(gdf.head())

    print("\nDataset shape:")
    print(gdf.shape)

    print("\nCoordinate Reference System:")
    print(gdf.crs)

    print("\nGeometry types:")
    print(gdf.geom_type.value_counts())

    print("\nMissing geometries:")
    print(gdf.geometry.isna().sum())

    print("\nGeometry validity:")
    print(gdf.geometry.is_valid.value_counts())

    # 5. Reproject to WGS 84 for GeoJSON export
    gdf_wgs84 = gdf.to_crs(epsg=4326)

    # 6. Create output folder and export
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    gdf_wgs84.to_file(
        output_dir / "river_district_analysis.geojson",
        driver="GeoJSON"
    )

    print("\nGeoJSON file saved successfully!")

finally:
    engine.dispose()
