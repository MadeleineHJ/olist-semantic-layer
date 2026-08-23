"""
Loads the 9 Olist CSVs from raw_data/ into DuckDB under a 'raw' schema.
No cleaning happens here, that's dbt's job.

Usage: python scripts/load_raw_data.py

Needs the CSVs downloaded first:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
(unzip into raw_data/)
"""

import duckdb
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"
DB_PATH = PROJECT_ROOT / "olist_warehouse.duckdb"
SCHEMA = "raw"

# csv filename -> table name
CSV_TO_TABLE = {
    "olist_customers_dataset.csv":                  "customers",
    "olist_geolocation_dataset.csv":                "geolocation",
    "olist_order_items_dataset.csv":                "order_items",
    "olist_order_payments_dataset.csv":             "order_payments",
    "olist_order_reviews_dataset.csv":              "order_reviews",
    "olist_orders_dataset.csv":                     "orders",
    "olist_products_dataset.csv":                   "products",
    "olist_sellers_dataset.csv":                    "sellers",
    "product_category_name_translation.csv":        "product_category_translation",
}


def validate_raw_data_dir() -> list[Path]:
    """Check that the raw_data directory exists and contains the expected CSVs."""

    if not RAW_DATA_DIR.exists():
        print(f"ERROR: Directory not found: {RAW_DATA_DIR}")
        print("Create it and place the Olist CSV files inside.")
        sys.exit(1)

    csv_files = list(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        print(f"ERROR: No CSV files found in {RAW_DATA_DIR}")
        print("Download the dataset from:")
        print("  https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        sys.exit(1)

    # Report which expected files are present / missing
    found = {f.name for f in csv_files}
    expected = set(CSV_TO_TABLE.keys())
    missing = expected - found
    extra = found - expected

    if missing:
        print(f"WARNING: Missing expected files: {missing}")
    if extra:
        print(f"NOTE:    Extra files (will be skipped): {extra}")

    return csv_files


def load_csvs_to_duckdb(csv_files: list[Path]) -> None:
    """Load each CSV into DuckDB under the raw schema."""

    con = duckdb.connect(str(DB_PATH))

    # Create the raw schema if it doesn't exist
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    loaded_count = 0

    for csv_path in csv_files:
        filename = csv_path.name

        if filename not in CSV_TO_TABLE:
            print(f"  SKIP   {filename} (not in expected file list)")
            continue

        table_name = CSV_TO_TABLE[filename]
        full_table_name = f"{SCHEMA}.{table_name}"

        # Drop and recreate to make the script idempotent
        con.execute(f"DROP TABLE IF EXISTS {full_table_name}")

        con.execute(f"""
            CREATE TABLE {full_table_name} AS
            SELECT *
            FROM read_csv_auto('{csv_path}', header=true, sample_size=-1)
        """)

        row_count = con.execute(f"SELECT COUNT(*) FROM {full_table_name}").fetchone()[0]
        col_count = len(
            con.execute(f"DESCRIBE {full_table_name}").fetchall()
        )

        print(f"  LOADED {full_table_name:<35} {row_count:>10,} rows  |  {col_count} columns")
        loaded_count += 1

    # summary of everything now in the raw schema
    print("\n" + "=" * 70)
    print(f"  DATABASE : {DB_PATH}")
    print(f"  SCHEMA   : {SCHEMA}")
    print(f"  TABLES   : {loaded_count}")
    print("=" * 70)

    tables = con.execute(f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = '{SCHEMA}'
        ORDER BY table_name
    """).fetchall()

    print("\n  Tables in raw schema:")
    for (t,) in tables:
        rc = con.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{t}").fetchone()[0]
        print(f"    {SCHEMA}.{t:<35} {rc:>10,} rows")

    con.close()
    print(f"\nDone. Database saved to {DB_PATH}")


def main():
    print("=" * 70)
    print("  Olist Raw Data Loader")
    print("=" * 70)
    print(f"\n  Source : {RAW_DATA_DIR}")
    print(f"  Target : {DB_PATH}")
    print(f"  Schema : {SCHEMA}\n")

    csv_files = validate_raw_data_dir()
    load_csvs_to_duckdb(csv_files)


if __name__ == "__main__":
    main()