# Phase 2 Findings: Grain and Tricky Spots

This document records the key data observations from profiling the raw Olist
data and the modeling decisions that flow from them. These decisions drive
the dbt staging and mart design in Phase 3 and beyond.

Profiling run: based on `scripts/profile_data.py`.

---

## 1. Date Range

| Field | Value |
|-------|-------|
| Earliest order | 2016-09-04 |
| Latest order | 2018-10-17 |
| Span | 773 days (~25 months) |

**Order volume by year:**

| Year | Orders |
|------|--------|
| 2016 | 329 |
| 2017 | 45,101 |
| 2018 | 54,011 |

**Note:** 2016 has only 329 orders (one quarter of activity) and is too
sparse for trend analysis. The dataset truncates in October 2018, so any
month-over-month chart needs to flag October 2018 as a partial month.

**Decision:**
- `dim_dates` spans 2016-09-01 through 2018-10-31
- Dashboards add visual flagging for 2016 and 2018-10 as "partial periods"

---

## 2. Customer Grain (CRITICAL)

| Field | Value |
|-------|-------|
| Total customer rows | 99,441 |
| Distinct `customer_id` | 99,441 |
| Distinct `customer_unique_id` | 96,096 |

**Repeat customer distribution:**

| Orders placed | Customers |
|---------------|-----------|
| 1 | 93,099 |
| 2 | 2,745 |
| 3 | 203 |
| 4 | 30 |
| 5 | 8 |
| 6 | 6 |
| 7 | 3 |
| 9 | 1 |
| 17 | 1 |

**Key insight:** 96.9% of customers buy exactly once. Repeat purchase is the
business's biggest growth opportunity. Note one customer placed 17 orders --
likely a B2B account or reseller; worth flagging as a power user segment.

**Decision:**
- `dim_customers` grain = `customer_unique_id`
- All customer-level metrics (LTV, repeat rate, churn) join on `customer_unique_id`
- `repeat_purchase_rate` becomes a headline KPI

---

## 3. Order Status Distribution

| Status | Orders | % |
|--------|--------|---|
| delivered | 96,478 | 97.02 |
| shipped | 1,107 | 1.11 |
| canceled | 625 | 0.63 |
| unavailable | 609 | 0.61 |
| invoiced | 314 | 0.32 |
| processing | 301 | 0.30 |
| created | 5 | 0.01 |
| approved | 2 | 0.00 |

**Decision:** Define multiple revenue metrics in the semantic layer:
- `revenue_gross` = all non-canceled, non-unavailable orders
- `revenue_net` = delivered orders only (the conservative number)
- `orders_count_completed` = delivered only
- `orders_count_total` = all statuses except canceled

Canceled + unavailable = 1,234 orders (~1.2%) excluded from revenue by default.

---

## 4. Order Items Grain

| Field | Value |
|-------|-------|
| Item rows | 112,650 |
| Distinct orders with items | 98,666 |
| Avg items per order | 1.14 |

**Items-per-order distribution:**

| Items | Orders |
|-------|--------|
| 1 | 88,863 (90.1%) |
| 2 | 7,516 |
| 3 | 1,322 |
| 4 | 505 |
| 5 | 204 |
| 6 | 198 |
| 7+ | 58 |

**Insight:** 775 orders (from the 99,441 total) have NO items. These map to
the canceled, unavailable, and other non-completed statuses. Need to handle
in joins: LEFT JOIN orders to items, not INNER JOIN, or revenue will silently
drop these orders.

**Decision:**
- `fact_order_items` at item grain (one row per item per order)
- `fact_orders` at order grain with pre-aggregated `n_items`, `total_item_price`, `total_freight`
- Pre-aggregate items BEFORE joining to payments or reviews

---

## 5. Payments Grain

| Field | Value |
|-------|-------|
| Payment rows | 103,886 |
| Distinct orders with payments | 99,440 |
| Avg payments per order | 1.045 |

**Payments-per-order distribution:**

| Payments | Orders |
|----------|--------|
| 1 | 96,479 |
| 2 | 2,382 |
| 3 | 301 |
| 4+ | 249 |

**Payment type distribution:**

| Type | Count |
|------|-------|
| credit_card | 76,795 (74%) |
| boleto | 19,784 (19%) |
| voucher | 5,775 |
| debit_card | 1,529 |
| not_defined | 3 |

**Data quality note:** 3 payments have `payment_type = 'not_defined'`. Edge case to flag in dbt tests.

**Insight:** 99,441 orders but only 99,440 have payments -- exactly 1 order is missing a payment record. Worth finding in dbt with a `relationships` test.

**Decision:**
- In `stg_order_payments`, aggregate to one row per order:
  - `total_payment_value` = SUM(payment_value)
  - `n_payment_methods` = COUNT(DISTINCT payment_type)
  - `primary_payment_type` = highest-value payment type
  - `total_installments` = MAX(payment_installments)
- Document the gap between `revenue_from_items` (sum of price + freight) and `revenue_from_payments` (sum of payment_value) -- they will not match exactly

---

## 6. Reviews Grain

| Field | Value |
|-------|-------|
| Review rows | 99,224 |
| Distinct `review_id` | 98,410 |
| Distinct `order_id` | 98,673 |

**Data quality finding:** `review_id` is NOT unique. 814 review IDs appear more than once in the raw data. This is a subtle but real data quality issue worth catching with a dbt test.

**Reviews-per-order:**

| Reviews | Orders |
|---------|--------|
| 1 | 98,126 |
| 2 | 543 |
| 3 | 4 |

**Review score distribution:**

| Score | Count | % |
|-------|-------|---|
| 1 (worst) | 11,424 | 11.5 |
| 2 | 3,151 | 3.2 |
| 3 | 8,179 | 8.2 |
| 4 | 19,142 | 19.3 |
| 5 (best) | 57,328 | 57.8 |

**Insight:** 11.5% of orders receive a 1-star review. That is a meaningful satisfaction problem and a natural narrative thread back to the regression work in Project 2.

**Decision:**
- In `stg_order_reviews`, deduplicate to one row per order:
  - `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC)`
  - Keep the most recent review when there are multiple
- Add `unique` test on `order_id` in the deduplicated staging model
- Surface the duplicate-review_id quirk in dbt docs

---

## 7. Delivery Performance (THE HEADLINE STORY)

| Field | Orders |
|-------|--------|
| Delivered | 96,476 |
| Not delivered | 2,965 |
| On-time (delivered <= estimated) | 88,649 |
| Late (delivered > estimated) | 7,827 |

**Avg delivery time:** 12.5 days (purchase to customer receipt)

**Review score by delivery outcome:**

| Delivery status | Avg score | Orders |
|-----------------|-----------|--------|
| on_time | 4.29 | 88,658 |
| late | 2.57 | 7,701 |
| not_delivered | 1.76 | 2,865 |

**This is the most important finding in the dataset.** Late deliveries drop average review score by 1.72 points, and undelivered orders drop it by 2.53 points. This is exactly the kind of business insight the regression project hinted at, and the semantic layer can now expose it as a first-class metric.

**Decision:**
- Add to `fact_orders`:
  - `delivery_days` (INT, days from purchase to delivery)
  - `is_on_time` (BOOLEAN)
  - `delivery_status` ENUM: 'on_time' | 'late' | 'not_delivered'
  - `days_late` (INT, NULL if on-time or not delivered)
- Add headline metric: `on_time_delivery_rate`
- Build a dashboard view that overlays delivery performance with review scores -- this becomes the showcase chart in the BI layer

---

## 8. Geolocation Duplicates

| Field | Value |
|-------|-------|
| Total rows | 1,000,163 |
| Distinct zip code prefixes | 19,015 |
| Avg rows per zip | 52.6 |

**Decision:**
- In `stg_geolocation`, aggregate to ONE row per zip code:
  - `AVG(lat)` and `AVG(lng)` for centroid
  - `MODE(city)` and `MODE(state)` for most-common label
- Never join `raw.geolocation` directly to anything else

---

## 9. Product Metadata Gaps

| Field | Count |
|-------|-------|
| Total products | 32,951 |
| Missing category | 610 (1.9%) |
| Missing weight | 2 |

**Decision:**
- In `stg_products`:
  - `COALESCE(product_category_name, 'uncategorized')`
  - Join `product_category_translation` and expose English category name
  - Drop the legacy Portuguese name from downstream models

---

## 10. Geographic Coverage

**Top 10 states by customer order volume:**

| State | Orders | % of total |
|-------|--------|------------|
| SP | 41,746 | 42.0 |
| RJ | 12,852 | 12.9 |
| MG | 11,635 | 11.7 |
| RS | 5,466 | 5.5 |
| PR | 5,045 | 5.1 |
| SC | 3,637 | 3.7 |
| BA | 3,380 | 3.4 |
| DF | 2,140 | 2.2 |
| ES | 2,033 | 2.0 |
| GO | 2,020 | 2.0 |

**Insight:** SP alone is 42% of orders. The top 3 states (SP, RJ, MG) are 67%.
Brazil's southeast dominates.

**Decision:**
- Add `is_southeast_region` boolean to `dim_customers` / `dim_geography`
- In dashboards, default to top-N state filtering or a "SP / RJ-MG / Other" grouping

---

## Metric Ambiguity Summary

The semantic layer in Phase 5 needs to resolve these explicitly. Each gets a named, documented metric, NOT a single fudged number.

| Ambiguity | Named metrics |
|-----------|---------------|
| "Customer" | always = `customer_unique_id` |
| "Revenue" | `revenue_net` (delivered), `revenue_gross` (non-canceled), `revenue_from_payments` |
| "Order count" | `orders_total`, `orders_completed`, `orders_canceled` |
| "Active customer" | `active_customers_90d`, `active_customers_365d` (lookback explicit) |
| "Average order value" | `aov_per_order` vs `aov_per_item` |
| "On-time delivery" | `on_time_delivery_rate` (delivered <= estimated) |

---

## Data Quality Issues to Encode as dbt Tests

| Issue | Test |
|-------|------|
| `customer_id` should be unique in customers | `unique` |
| `review_id` is NOT unique in raw -- expected | documented in dbt docs |
| `order_id` unique in deduplicated reviews | `unique` |
| 3 payments have `payment_type = 'not_defined'` | `accepted_values` warn |
| 775 orders have no items | join behavior documented |
| 1 order has no payment | `relationships` test surfaces it |
| 610 products lack category | handled with COALESCE in staging |
| 2,965 orders have NULL delivery date | `not_delivered` status, expected |

---

## Phase 3 Pre-flight Checklist

Before writing the first dbt model:

- [x] dim_customers grain = customer_unique_id
- [x] fact_order_items grain = item
- [x] fact_orders grain = order (pre-aggregated)
- [x] Keep latest review per order
- [x] Aggregate geolocation to one row per zip
- [x] COALESCE missing categories to 'uncategorized'
- [x] Define `revenue_net` and `revenue_gross` separately
- [x] Date dimension covers 2016-09 -> 2018-10
- [x] Status filtering is per-metric, not global
- [x] Identified data quality issues to encode as tests