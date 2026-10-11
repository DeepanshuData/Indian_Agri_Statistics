
# PostgreSQL to Pandas Agriculture Analytics Pipeline

## 1. Project Overview

This project connects a PostgreSQL database to Python and Pandas to
analyze Indian agriculture statistics.

The pipeline loads data from the `public.agriculture` table in the
`agriculture_db` database. It then inspects and cleans the data,
performs numerical calculations, creates grouped summaries, combines
results, generates a pivot table, and saves charts.

## 2. Technologies Used

- Python
- PostgreSQL
- Pandas
- NumPy
- SQLAlchemy
- Psycopg
- Matplotlib
- python-dotenv

## 3. Data Source

Database: `agriculture_db`

Table: `public.agriculture`

Columns:

- `state`
- `district`
- `crop`
- `year`
- `season`
- `area`
- `production`
- `yield`

The database credentials are stored locally in `.env`. Never commit
the real `.env` file or share database passwords publicly.

## 4. Project Structure

```text
Indian_Agri_Statistics/
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── src/
│   ├── db_connection.py
│   └── week1_pandas_pipeline.py
├── docs/
│   └── postgresql_pandas_pipeline.md
└── output/
    ├── cleaned_agriculture_data.csv
    ├── crop_summary.csv
    ├── state_summary.csv
    ├── state_leading_crop_summary.csv
    ├── state_season_production_pivot.csv
    ├── pipeline_summary.json
    └── charts/
        ├── top_10_crops_production.png
        └── top_10_states_production.png
```

The `output/` files are generated when the pipeline runs.

## 5. Installation

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a local `.env` file using `.env.example` as a template. Set
the correct PostgreSQL username, password, host, port, and database.

## 6. Run the Pipeline

Test the database connection:

```powershell
python .\src\db_connection.py
```

Run the full analysis:

```powershell
python .\src\week1_pandas_pipeline.py
```

## 7. Pipeline Stages

1. Load the agriculture table from PostgreSQL.
2. Inspect columns, data types, missing values, duplicates, and
   numerical statistics.
3. Remove exact duplicate rows, normalize text fields, and convert
   numerical columns.
4. Use NumPy for array-based calculations.
5. Use Pandas `groupby()` to summarize crops and states.
6. Use Pandas `merge()` to combine leading-crop and state summaries.
7. Use `pivot_table()` to summarize production by state and season.
8. Use Matplotlib to generate production charts.
9. Save summary data and pipeline metadata.

## 8. Generated Outputs

- `cleaned_agriculture_data.csv`: cleaned records.
- `crop_summary.csv`: total area, production, average yield, and
  record count by crop.
- `state_summary.csv`: total area, production, and average yield
  by state.
- `state_leading_crop_summary.csv`: leading crop by production for
  each state, combined with state-level statistics.
- `state_season_production_pivot.csv`: production by state and season.
- `pipeline_summary.json`: source information, row counts, and
  counts of unique geographic and crop categories.
- `charts/`: PNG charts for top crops and states by production.

## 9. Data Quality Notes

Exact duplicate rows are removed. Blank text fields are converted
to missing values, and rows without essential grouping fields are
excluded.

Missing numerical values are not automatically imputed. Production
totals and average yields should be interpreted in light of the
dataset's original units and reporting practices.

The pipeline exports a CSV for analysis, but PostgreSQL remains the
source of the data.

## 10. Security

- Keep `.env` private.
- Commit `.env.example`, not `.env`.
- Never put database passwords in source code.
- Do not commit the virtual environment.
- Review Git status and staged files before every commit.
