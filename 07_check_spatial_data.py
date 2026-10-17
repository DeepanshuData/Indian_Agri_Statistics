from getpass import getpass

from sqlalchemy import create_engine, URL, text

connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres",
    password=getpass("Enter your PostgreSQL password: "),
    host="localhost",
    port=5432,
    database="agriculture_db"
)

engine = create_engine(connection_url)

queries = {
    "District CRS": """
        SELECT
            ST_SRID(geom) AS srid,
            GeometryType(geom) AS geometry_type,
            COUNT(*) AS feature_count
        FROM public.indian_districts_7755
        GROUP BY ST_SRID(geom), GeometryType(geom);
    """,
    "River buffer CRS": """
        SELECT
            ST_SRID(geom) AS srid,
            GeometryType(geom) AS geometry_type,
            COUNT(*) AS feature_count
        FROM public.river_buffer_5km
        GROUP BY ST_SRID(geom), GeometryType(geom);
    """,
    "District area check": """
        SELECT
            MIN(ST_Area(geom) / 1000000.0) AS min_area_sq_km,
            MAX(ST_Area(geom) / 1000000.0) AS max_area_sq_km
        FROM public.indian_districts_7755;
    """
}

try:
    with engine.connect() as connection:
        for title, query in queries.items():
            print(f"\n--- {title} ---")
            result = connection.execute(text(query))
            for row in result:
                print(row)

finally:
    engine.dispose()
