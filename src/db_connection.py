
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text

# Load database settings from the project's .env file
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Read database configuration
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", "5432"))
db_name = os.getenv("DB_NAME", "agriculture_db")

# Check required configuration
if not db_user or not db_password:
    raise ValueError(
        "DB_USER or DB_PASSWORD is missing. Check your .env file."
    )

# Create a safe PostgreSQL connection URL
database_url = URL.create(
    drivername="postgresql+psycopg",
    username=db_user,
    password=db_password,
    host=db_host,
    port=db_port,
    database=db_name,
)

# Create the SQLAlchemy engine
engine = create_engine(database_url, pool_pre_ping=True)


def load_agriculture_data():
    """Load agriculture records from PostgreSQL into Pandas."""

    query = text("""
        SELECT
            state,
            district,
            crop,
            year,
            season,
            area,
            production,
            "yield"
        FROM public.agriculture
    """)

    with engine.connect() as connection:
        df = pd.read_sql_query(query, connection)

    return df


if __name__ == "__main__":
    try:
        df = load_agriculture_data()

        print("PostgreSQL connection successful!")
        print("Database:", db_name)
        print("Table: public.agriculture")
        print("Dataset shape:", df.shape)

        print("\nFirst five rows:")
        print(df.head())

        print("\nColumn information:")
        df.info()

        print("\nMissing values:")
        print(df.isnull().sum())

        print("\nExact duplicate rows:", df.duplicated().sum())

    finally:
        engine.dispose()
