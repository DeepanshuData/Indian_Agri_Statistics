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

query = """
SELECT
    d.gid AS district_id,
    d.statename,
    d.distname
FROM public.indian_districts_7755 AS d
LEFT JOIN public.river_buffer_district_analysis AS a
    ON d.gid = a.district_id
WHERE a.district_id IS NULL
ORDER BY d.statename, d.distname;
"""

try:
    with engine.connect() as connection:
        rows = connection.execute(text(query)).fetchall()

        print("\nDistricts absent from the analysis table:")
        for row in rows:
            print(row)

        print("\nNumber of absent district IDs:", len(rows))

finally:
    engine.dispose()
