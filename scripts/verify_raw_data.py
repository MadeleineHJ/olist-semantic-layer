"""
Verify Raw Data Load
=====================
Run this after load_raw_data.py to confirm everything loaded correctly
and get a quick profile of each table (nulls, types, sample values).

Usage:
    python scripts/verify_raw_data.py
"""

import duckdb
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "olist_warehouse.duckdb"
SCHEMA = "raw"


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run load_raw_data.py first.")
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    tables = con.execute(f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = '{SCHEMA}'
        ORDER BY table_name
    """).fetchall()

    if not tables:
        print(f"ERROR: No tables found in schema '{SCHEMA}'")
        sys.exit(1)

    print("=" * 70)
    print("  Raw Data Verification Report")
    print("=" * 70)

    for (table_name,) in tables:
        full_name = f"{SCHEMA}.{table_name}"
        row_count = con.execute(f"SELECT COUNT(*) FROM {full_name}").fetchone()[0]

        print(f"\n{'─' * 70}")
        print(f"  TABLE: {full_name}  ({row_count:,} rows)")
        print(f"{'─' * 70}")

        # Column details: name, type, null count, null %
        columns = con.execute(f"DESCRIBE {full_name}").fetchall()

        print(f"  {'Column':<40} {'Type':<15} {'Nulls':>8} {'Null%':>7}")
        print(f"  {'─'*40} {'─'*15} {'─'*8} {'─'*7}")

        for col in columns:
            col_name = col[0]
            col_type = col[1]
            null_count = con.execute(
                f'SELECT COUNT(*) FROM {full_name} WHERE "{col_name}" IS NULL'
            ).fetchone()[0]
            null_pct = (null_count / row_count * 100) if row_count > 0 else 0

            flag = " <<<" if null_pct > 10 else ""
            print(
                f"  {col_name:<40} {col_type:<15} {null_count:>8,} {null_pct:>6.1f}%{flag}"
            )

    # Quick relationship check: do key joins work?
    print(f"\n{'=' * 70}")
    print("  Key Relationship Checks")
    print(f"{'=' * 70}")

    checks = [
        (
            "orders -> customers (customer_id)",
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.orders o
            LEFT JOIN {SCHEMA}.customers c ON o.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
            """,
        ),
        (
            "order_items -> orders (order_id)",
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.order_items oi
            LEFT JOIN {SCHEMA}.orders o ON oi.order_id = o.order_id
            WHERE o.order_id IS NULL
            """,
        ),
        (
            "order_items -> products (product_id)",
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.order_items oi
            LEFT JOIN {SCHEMA}.products p ON oi.product_id = p.product_id
            WHERE p.product_id IS NULL
            """,
        ),
        (
            "order_items -> sellers (seller_id)",
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.order_items oi
            LEFT JOIN {SCHEMA}.sellers s ON oi.seller_id = s.seller_id
            WHERE s.seller_id IS NULL
            """,
        ),
        (
            "order_payments -> orders (order_id)",
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.order_payments op
            LEFT JOIN {SCHEMA}.orders o ON op.order_id = o.order_id
            WHERE o.order_id IS NULL
            """,
        ),
    ]

    for label, query in checks:
        orphans = con.execute(query).fetchone()[0]
        status = "PASS" if orphans == 0 else f"FAIL ({orphans:,} orphans)"
        print(f"  {label:<50} {status}")

    con.close()
    print(f"\nVerification complete.\n")


if __name__ == "__main__":
    main()