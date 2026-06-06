"""
Phase 2: Profile Grain and Tricky Spots
========================================
Runs a series of investigations against the raw Olist data to expose
the modeling decisions you need to make BEFORE writing dbt models.

Each section prints a finding and (where relevant) a "Modeling Implication"
line. Capture those in docs/phase2_findings.md as you go.

Usage:
    python scripts/profile_data.py
"""

import duckdb
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "olist_warehouse.duckdb"
SCHEMA = "raw"


def section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def subsection(title: str) -> None:
    print(f"\n  -- {title}")


def query(con, sql: str):
    return con.execute(sql).fetchall()


def show(rows, headers=None):
    """Print query results as a simple table."""
    if not rows:
        print("    (no rows)")
        return
    if headers:
        print("    " + " | ".join(f"{h:<20}" for h in headers))
        print("    " + "-" * (22 * len(headers)))
    for row in rows:
        print("    " + " | ".join(f"{str(v):<20}" for v in row))


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    # =====================================================================
    # 1. DATE RANGE -- what time period does the data cover?
    # =====================================================================
    section("1. DATE RANGE")

    rows = query(con, f"""
        SELECT
            MIN(order_purchase_timestamp)::DATE AS earliest_order,
            MAX(order_purchase_timestamp)::DATE AS latest_order,
            DATE_DIFF('day',
                MIN(order_purchase_timestamp),
                MAX(order_purchase_timestamp)) AS span_days
        FROM {SCHEMA}.orders
    """)
    show(rows, ["earliest_order", "latest_order", "span_days"])

    subsection("Orders by year")
    rows = query(con, f"""
        SELECT
            EXTRACT(YEAR FROM order_purchase_timestamp) AS year,
            COUNT(*) AS order_count
        FROM {SCHEMA}.orders
        GROUP BY 1 ORDER BY 1
    """)
    show(rows, ["year", "order_count"])

    print("""
  >>> MODELING IMPLICATION
      Build dim_dates covering the full span. Note 2016 and the tail of 2018
      have very few orders -- worth flagging in dashboards so trend lines
      don't mislead viewers.""")

    # =====================================================================
    # 2. CUSTOMER GRAIN -- the famous customer_id vs customer_unique_id trap
    # =====================================================================
    section("2. CUSTOMER GRAIN (the critical trap)")

    rows = query(con, f"""
        SELECT
            COUNT(*)                            AS total_rows,
            COUNT(DISTINCT customer_id)         AS distinct_customer_id,
            COUNT(DISTINCT customer_unique_id)  AS distinct_customer_unique_id
        FROM {SCHEMA}.customers
    """)
    show(rows, ["total_rows", "customer_id", "customer_unique_id"])

    subsection("Customers with multiple orders (i.e. multiple customer_ids)")
    rows = query(con, f"""
        SELECT
            n_orders,
            COUNT(*) AS n_customers
        FROM (
            SELECT customer_unique_id, COUNT(*) AS n_orders
            FROM {SCHEMA}.customers
            GROUP BY 1
        )
        GROUP BY 1 ORDER BY 1
        LIMIT 10
    """)
    show(rows, ["orders_placed", "n_customers"])

    print("""
  >>> MODELING IMPLICATION
      customer_id is a PER-ORDER identifier, NOT a person.
      customer_unique_id is the real person.

      In dim_customers, the grain MUST be customer_unique_id.
      For "repeat customer" or "customer lifetime value" metrics,
      always use customer_unique_id. Using customer_id will make
      every customer look like a one-time buyer.""")

    # =====================================================================
    # 3. ORDER STATUS DISTRIBUTION -- what counts as a "real" order?
    # =====================================================================
    section("3. ORDER STATUS DISTRIBUTION")

    rows = query(con, f"""
        SELECT
            order_status,
            COUNT(*) AS n_orders,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM {SCHEMA}.orders
        GROUP BY 1 ORDER BY 2 DESC
    """)
    show(rows, ["status", "n_orders", "pct"])

    print("""
  >>> MODELING IMPLICATION
      'delivered' is the only status that represents a completed transaction.
      'canceled' should be excluded from revenue.
      'shipped', 'processing', 'invoiced', 'approved', 'created' are
      in-flight orders -- may or may not count depending on the metric.
      'unavailable' = order placed but product unavailable.

      This is one of the headline metric ambiguities your semantic layer
      will solve. Define revenue_gross (all paid orders) vs
      revenue_net (delivered only) and let the user choose.""")

    # =====================================================================
    # 4. ORDER ITEMS GRAIN -- the multiplication trap
    # =====================================================================
    section("4. ORDER ITEMS GRAIN")

    rows = query(con, f"""
        SELECT
            COUNT(*)                  AS total_item_rows,
            COUNT(DISTINCT order_id)  AS distinct_orders
        FROM {SCHEMA}.order_items
    """)
    show(rows, ["total_item_rows", "distinct_orders"])

    subsection("Distribution of items per order")
    rows = query(con, f"""
        SELECT
            items_in_order,
            COUNT(*) AS n_orders
        FROM (
            SELECT order_id, COUNT(*) AS items_in_order
            FROM {SCHEMA}.order_items
            GROUP BY 1
        )
        GROUP BY 1 ORDER BY 1
        LIMIT 15
    """)
    show(rows, ["items_in_order", "n_orders"])

    print("""
  >>> MODELING IMPLICATION
      order_items is at the ITEM grain, not the order grain.
      An order with 3 items produces 3 rows here.

      If you join orders -> order_items and then sum 'price' at the
      order level WITHOUT being careful, you will NOT multiply (good).
      But if you join order_items -> order_payments without aggregating
      first, you WILL get a Cartesian explosion.

      Build fact_order_items at ITEM grain (one row per item).
      Pre-aggregate to order grain BEFORE joining to payments or reviews.""")

    # =====================================================================
    # 5. PAYMENTS GRAIN -- multiple payment methods per order
    # =====================================================================
    section("5. PAYMENTS GRAIN")

    rows = query(con, f"""
        SELECT
            COUNT(*)                                 AS total_payment_rows,
            COUNT(DISTINCT order_id)                 AS distinct_orders,
            ROUND(COUNT(*)::DECIMAL
                  / COUNT(DISTINCT order_id), 3)     AS avg_payments_per_order
        FROM {SCHEMA}.order_payments
    """)
    show(rows, ["total_payment_rows", "distinct_orders", "avg_per_order"])

    subsection("Orders with multiple payment records")
    rows = query(con, f"""
        SELECT
            payments_per_order,
            COUNT(*) AS n_orders
        FROM (
            SELECT order_id, COUNT(*) AS payments_per_order
            FROM {SCHEMA}.order_payments
            GROUP BY 1
        )
        GROUP BY 1 ORDER BY 1
        LIMIT 10
    """)
    show(rows, ["payments_per_order", "n_orders"])

    subsection("Payment type distribution")
    rows = query(con, f"""
        SELECT payment_type, COUNT(*) AS n
        FROM {SCHEMA}.order_payments
        GROUP BY 1 ORDER BY 2 DESC
    """)
    show(rows, ["payment_type", "n"])

    print("""
  >>> MODELING IMPLICATION
      An order can have multiple payment rows (e.g. credit card + voucher).
      To get total paid per order, SUM(payment_value) GROUP BY order_id.

      Note: payment_value SUM per order will often differ slightly from
      SUM(price + freight_value) in order_items due to vouchers and
      installment fees. This is another metric definition choice:
      "revenue" = sum of item prices? or sum of payments collected?
      Document both.""")

    # =====================================================================
    # 6. REVIEWS GRAIN -- duplicate reviews and timing
    # =====================================================================
    section("6. REVIEWS GRAIN")

    rows = query(con, f"""
        SELECT
            COUNT(*)                  AS total_review_rows,
            COUNT(DISTINCT review_id) AS distinct_review_ids,
            COUNT(DISTINCT order_id)  AS distinct_orders
        FROM {SCHEMA}.order_reviews
    """)
    show(rows, ["total_rows", "distinct_review_ids", "distinct_orders"])

    subsection("Orders with multiple reviews")
    rows = query(con, f"""
        SELECT
            reviews_per_order,
            COUNT(*) AS n_orders
        FROM (
            SELECT order_id, COUNT(*) AS reviews_per_order
            FROM {SCHEMA}.order_reviews
            GROUP BY 1
        )
        GROUP BY 1 ORDER BY 1
        LIMIT 10
    """)
    show(rows, ["reviews_per_order", "n_orders"])

    subsection("Review score distribution")
    rows = query(con, f"""
        SELECT review_score, COUNT(*) AS n,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM {SCHEMA}.order_reviews
        GROUP BY 1 ORDER BY 1
    """)
    show(rows, ["score", "n", "pct"])

    print("""
  >>> MODELING IMPLICATION
      Most orders have exactly one review, but a small number have multiple.
      Decide: keep the latest review per order (recommended) or average?

      In stg_order_reviews, deduplicate to one row per order using
      ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC).""")

    # =====================================================================
    # 7. DELIVERY PERFORMANCE -- on-time vs late
    # =====================================================================
    section("7. DELIVERY PERFORMANCE")

    rows = query(con, f"""
        SELECT
            COUNT(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL) AS delivered,
            COUNT(*) FILTER (WHERE order_delivered_customer_date IS NULL)     AS not_delivered,
            COUNT(*) FILTER (
                WHERE order_delivered_customer_date IS NOT NULL
                  AND order_delivered_customer_date <= order_estimated_delivery_date
            ) AS on_time,
            COUNT(*) FILTER (
                WHERE order_delivered_customer_date IS NOT NULL
                  AND order_delivered_customer_date > order_estimated_delivery_date
            ) AS late
        FROM {SCHEMA}.orders
    """)
    show(rows, ["delivered", "not_delivered", "on_time", "late"])

    subsection("Average delivery days (purchase -> customer receipt)")
    rows = query(con, f"""
        SELECT
            ROUND(AVG(DATE_DIFF('day',
                order_purchase_timestamp,
                order_delivered_customer_date)), 1) AS avg_days
        FROM {SCHEMA}.orders
        WHERE order_delivered_customer_date IS NOT NULL
    """)
    show(rows, ["avg_delivery_days"])

    subsection("Review score by on-time vs late delivery")
    rows = query(con, f"""
        SELECT
            CASE
                WHEN o.order_delivered_customer_date IS NULL THEN 'not_delivered'
                WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                    THEN 'on_time'
                ELSE 'late'
            END AS delivery_status,
            ROUND(AVG(r.review_score), 2) AS avg_score,
            COUNT(*) AS n
        FROM {SCHEMA}.orders o
        JOIN {SCHEMA}.order_reviews r ON o.order_id = r.order_id
        GROUP BY 1 ORDER BY 2 DESC
    """)
    show(rows, ["delivery_status", "avg_score", "n"])

    print("""
  >>> MODELING IMPLICATION
      Late deliveries strongly correlate with lower review scores.
      This is the headline narrative connection back to Project 2's
      satisfaction work. Make sure fact_orders carries:
        - delivery_days (computed)
        - is_on_time (boolean)
        - delivery_status (on_time / late / not_delivered)
      and that fact_reviews can join cleanly to expose this story.""")

    # =====================================================================
    # 8. GEOLOCATION DUPLICATES
    # =====================================================================
    section("8. GEOLOCATION DUPLICATES")

    rows = query(con, f"""
        SELECT
            COUNT(*)                                  AS total_rows,
            COUNT(DISTINCT geolocation_zip_code_prefix) AS distinct_zips,
            ROUND(COUNT(*)::DECIMAL
                  / COUNT(DISTINCT geolocation_zip_code_prefix), 1) AS avg_rows_per_zip
        FROM {SCHEMA}.geolocation
    """)
    show(rows, ["total_rows", "distinct_zips", "avg_rows_per_zip"])

    print("""
  >>> MODELING IMPLICATION
      geolocation has many rows per zip code (multiple lat/lng samples).
      DO NOT join it directly to customers or sellers -- you'll multiply rows.

      In stg_geolocation, aggregate to one row per zip:
        AVG(lat), AVG(lng), MODE(city), MODE(state) GROUP BY zip_code_prefix.""")

    # =====================================================================
    # 9. PRODUCTS WITH MISSING METADATA
    # =====================================================================
    section("9. PRODUCT METADATA GAPS")

    rows = query(con, f"""
        SELECT
            COUNT(*)                                            AS total_products,
            COUNT(*) FILTER (WHERE product_category_name IS NULL) AS missing_category,
            COUNT(*) FILTER (WHERE product_weight_g IS NULL)      AS missing_weight
        FROM {SCHEMA}.products
    """)
    show(rows, ["total_products", "missing_category", "missing_weight"])

    print("""
  >>> MODELING IMPLICATION
      ~610 products (1.9%) have no category. In stg_products, coalesce
      to 'uncategorized' so they still appear in category-level reports.
      The category translation table maps Portuguese -> English; do
      that join in stg_products so downstream models see English only.""")

    # =====================================================================
    # 10. STATE COVERAGE
    # =====================================================================
    section("10. GEOGRAPHIC COVERAGE")

    subsection("Top 10 customer states by order volume")
    rows = query(con, f"""
        SELECT c.customer_state, COUNT(DISTINCT o.order_id) AS n_orders
        FROM {SCHEMA}.orders o
        JOIN {SCHEMA}.customers c ON o.customer_id = c.customer_id
        GROUP BY 1 ORDER BY 2 DESC
        LIMIT 10
    """)
    show(rows, ["state", "orders"])

    print("""
  >>> MODELING IMPLICATION
      Sao Paulo (SP) will dominate. For dashboards, consider showing
      "SP vs rest of Brazil" as a toggle, or normalizing by population.""")

    # =====================================================================
    # SUMMARY
    # =====================================================================
    section("PHASE 2 SUMMARY -- DECISIONS TO RECORD")
    print("""
  Document these in docs/phase2_findings.md before starting dbt:

    1. dim_customers grain     = customer_unique_id (not customer_id)
    2. fact_order_items grain  = item (one row per item per order)
    3. fact_orders grain       = order (pre-aggregate items first)
    4. Review dedup            = latest review_creation_date per order
    5. Geolocation handling    = aggregate to one row per zip
    6. Missing categories      = coalesce to 'uncategorized'
    7. Revenue definitions     = gross (all) vs net (delivered only)
    8. Payment vs item totals  = document as separate metrics
    9. Date dimension          = cover 2016-09 through 2018-10
   10. Status filter           = decide per metric, not globally
""")

    con.close()


if __name__ == "__main__":
    main()