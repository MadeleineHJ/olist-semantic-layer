"""
Profiles the raw Olist tables for grain issues and other gotchas before
any dbt model gets written -- customer_id vs customer_unique_id, item/
payment/review fan-out, geolocation duplicates, etc. Findings from this
run are what docs/phase2_findings.md is based on.

Usage: python scripts/profile_data.py
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
      -> dim_dates should cover the full span. 2016 and the tail of 2018
         are both thin months -- flag those as partial periods in any
         trend chart or they'll read as a real dip.""")

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
      -> customer_id is per order, not per person -- customer_unique_id
         is the real person. dim_customers has to be built on
         customer_unique_id or every repeat buyer looks like a
         one-time customer.""")

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
      -> only 'delivered' is a completed transaction. 'canceled' shouldn't
         count toward revenue at all. everything else (shipped, processing,
         invoiced, approved, created, unavailable) is in some in-flight or
         dead-end state -- whether it counts depends on which revenue
         number you're asked for, hence revenue_gross vs revenue_net later.""")

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
      -> order_items is item grain, not order grain -- 3 items = 3 rows.
         summing price grouped by order is fine, but joining order_items
         straight to order_payments without aggregating first would
         fan out badly. pre-aggregate to order grain before that join.""")

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
      -> an order can have several payment rows (credit card + voucher,
         say), so total paid = SUM(payment_value) GROUP BY order_id.
         that total won't match SUM(price + freight) from order_items
         exactly -- vouchers and installment fees explain the gap. worth
         keeping both as separate, named metrics rather than picking one.""")

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
      -> a handful of orders have more than one review. going with
         latest-review-wins (ROW_NUMBER partitioned by order_id, ordered
         by review_creation_date desc) rather than averaging them.""")

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
      -> this is the headline finding -- late delivery tanks review
         scores. fact_orders needs delivery_days, is_on_time, and
         delivery_status so this relationship is queryable later,
         not something you'd have to recompute by hand.""")

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
      -> way too many rows per zip to join this raw. aggregate first --
         avg lat/lng, mode city/state, grouped by zip_code_prefix.""")

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
      -> ~610 products (1.9%) have no category -- coalesce to
         'uncategorized' in staging instead of dropping them from
         category reports. do the PT->EN translation join there too.""")

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
      -> Sao Paulo alone will dominate every chart. Worth a "SP vs rest
         of Brazil" toggle on dashboards rather than one long state list.""")

    section("SUMMARY")
    print("""
  Decisions this run feeds into docs/phase2_findings.md:

    - dim_customers grain: customer_unique_id, not customer_id
    - fact_order_items: item grain; fact_orders: pre-aggregated order grain
    - reviews: keep latest per order, don't average
    - geolocation: aggregate to one row per zip before joining anywhere
    - missing product categories: coalesce to 'uncategorized'
    - revenue: gross (non-canceled) vs net (delivered) as separate metrics
    - date dimension: cover 2016-09 through 2018-10
    - status filtering: decided per metric, not with one global rule
""")

    con.close()


if __name__ == "__main__":
    main()