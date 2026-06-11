# Metrics Catalog

This is the governed source of truth for every business metric in the Olist
semantic layer. Each metric has exactly **one** definition here. When someone
asks "what was our revenue last quarter?", this catalog determines the answer,
not whichever analyst happened to write the query.

The metrics are defined declaratively in `dbt_project/models/marts/_metrics.yml`
on top of semantic models in `_semantic_models.yml`, and queried with MetricFlow.

---

## Why a semantic layer?

In Phase 2 profiling we found that several "obvious" metrics have more than one
defensible definition. Left unmanaged, this produces the classic problem where
three dashboards report three different revenue numbers and nobody trusts any of
them. The semantic layer resolves this by defining each interpretation as a
separate, explicitly named, documented metric. Ambiguity is made visible and
deliberate instead of hidden in SQL.

---

## How to query

From the `dbt_project/` directory (with `DBT_PROFILES_DIR` set):

```bash
# List every metric and the dimensions it can be sliced by
mf list metrics

# A single metric
mf query --metrics revenue_net

# Multiple metrics, grouped by month
mf query --metrics revenue_net,orders_completed --group-by metric_time__month

# Sliced by a categorical dimension
mf query --metrics revenue_net --group-by order__order_status

# Sliced by customer geography (joins orders -> customers automatically)
mf query --metrics revenue_net --group-by customer__customer_state

# See the SQL MetricFlow generates, without running it
mf query --metrics on_time_delivery_rate --explain
```

---

## Metric definitions

### Volume

| Metric | Definition | Notes |
|--------|------------|-------|
| `orders_total` | Count of all orders, any status | Top-of-funnel volume. Includes canceled and undelivered. |
| `orders_completed` | Count of `delivered` orders only | The conservative "real sales" count. |
| `orders_on_time` | Count of orders delivered on or before the estimate | Building block for the on-time rate. |
| `orders_reviewed` | Count of orders that received a review | Building block for review coverage. |

### Revenue (the headline ambiguity)

Three legitimate definitions of "revenue", each named explicitly:

| Metric | Definition | Business reasoning |
|--------|------------|--------------------|
| `revenue_gross` | Sum of item prices for all **non-canceled** orders | Optimistic figure. Counts orders that are in-flight (shipped, processing) but not yet delivered. |
| `revenue_net` | Sum of item prices for **delivered** orders only | Conservative figure finance would recognize. The default "revenue" for most reporting. |
| `revenue_collected` | Sum of **payments** collected on delivered orders | Includes freight and installment/voucher amounts, so it differs from `revenue_net` by design. Reconciles to cash, not catalog price. |

All three exclude freight from the "item" figures except `revenue_collected`,
which is payment-based. The gap between `revenue_net` and `revenue_collected`
is itself a useful signal (freight burden + payment fees).

### Average order value

| Metric | Definition | Notes |
|--------|------------|-------|
| `average_order_value` | `revenue_net` / `orders_completed` | Per-ORDER, not per-item. An order with 3 items is one denominator unit. |

### Delivery performance (the headline operational story)

| Metric | Definition | Notes |
|--------|------------|-------|
| `on_time_delivery_rate` | `orders_on_time` / `orders_completed` | Share of delivered orders that met the promised date. Strongly correlated with review score (see below). |

### Satisfaction (ties back to Project 2)

| Metric | Definition | Notes |
|--------|------------|-------|
| `average_review_score` | Mean of `review_score` (1-5) | Orders without a review are excluded from the average. |
| `review_coverage_rate` | `orders_reviewed` / `orders_total` | What fraction of orders we actually have feedback on. Context for how much to trust the average. |

---

## The relationship that motivates the whole project

Querying `average_review_score` sliced by `order__delivery_status` reproduces
the core finding from Phase 2:

| delivery_status | average_review_score |
|-----------------|----------------------|
| on_time | ~4.29 |
| late | ~2.57 |
| not_delivered | ~1.76 |

On-time delivery is the single largest lever on customer satisfaction in this
dataset. `on_time_delivery_rate` and `average_review_score` are therefore the
two metrics a Olist operations team should watch together.

---

## Dimensions available

Order metrics can be sliced by:

- **Time:** `metric_time__day`, `metric_time__week`, `metric_time__month`, `metric_time__quarter`, `metric_time__year` (via the `dim_dates` time spine)
- **Order:** `order__order_status`, `order__delivery_status`, `order__primary_payment_type`
- **Customer:** `customer__customer_state`, `customer__is_southeast_region` (joined automatically through the shared `customer` entity)

---

## Design decisions worth noting

- **Customer grain.** All customer slicing uses `customer_unique_id` (the real person), never the per-order `customer_id`. See `docs/phase2_findings.md` section 2.
- **The `customers` semantic model has no measures.** It exists purely as a dimension source so order metrics can be sliced by geography. A measure there would need a time dimension that `dim_customers` does not have.
- **Status filtering is per-metric.** There is no global "exclude canceled" rule. Each metric states its own filter, because the right treatment of canceled and undelivered orders depends on the question being asked.
- **Ratio metrics are built from other metrics.** `on_time_delivery_rate`, `review_coverage_rate`, and `average_order_value` reference named numerator and denominator metrics rather than raw measures, which keeps each component independently queryable and documented.

---

## Extending the layer

Natural next metrics once the basics are in place:

- `repeat_purchase_rate`: share of customers with more than one completed order (needs a customer-level order-count measure, likely via a dedicated mart).
- `active_customers_90d` / `active_customers_365d`: distinct customers with a completed order in a trailing window (a cumulative/windowed metric).
- `revenue_per_customer`: `revenue_net` / `customers_total`.
- Category-level metrics by joining `fact_order_items` to `dim_products` in a second semantic model at item grain.