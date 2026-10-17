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
    "CRS definition": """
        SELECT
            srid,
            auth_name,
            auth_srid,
            srtext,
            proj4text
        FROM spatial_ref_sys
        WHERE srid = 7755;
    """,
    "District feature count": """
        SELECT COUNT(*) AS feature_count
        FROM public.indian_districts_7755;
    """,
    "Distinct district IDs": """
        SELECT COUNT(DISTINCT gid) AS distinct_ids
        FROM public.indian_districts_7755;
    """,
    "District analysis table count": """
        SELECT COUNT(*) AS feature_count
        FROM public.river_buffer_district_analysis;
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
