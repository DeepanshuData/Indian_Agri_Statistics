
from getpass import getpass
from sqlalchemy import create_engine, text, URL

username = "postgres"
password = getpass("Enter your PostgreSQL password: ")

connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username=username,
    password=password,
    host="localhost",
    port=5432,
    database="agriculture_db"
)

engine = create_engine(connection_url)

try:
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version();")
        ).scalar()

        print("\nConnection successful!")
        print(version)

        tables = connection.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
        ).scalars().all()

        print("\nDatabase tables:")
        for table in tables:
            print(table)
finally:
    engine.dispose()
