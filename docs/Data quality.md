# Data Quality & Testing Strategy

This project treats data quality as a first-class concern. Every model is
covered by automated tests that run on every `dbt build`, so a broken
assumption fails loudly during development instead of silently reaching a
dashboard. This document explains the testing approach, the severity model,
and the known data issues we deliberately accept.

---

## Testing philosophy

Tests are layered to match where problems originate:

1. **Source tests** catch issues in the raw Kaggle data before transformation (uniqueness of keys, accepted status values, referential integrity).
2. **Staging tests** verify our cleaning did what we intended (grain preserved, deduplication worked, types and ranges sane).
3. **Mart tests** protect the analytical contract the BI layer depends on (dimension keys unique, fact-to-dimension relationships intact, measures within plausible ranges).
4. **Singular tests** encode cross-model business rules that no single column test can express (revenue reconciliation, grain preservation across joins).

Total coverage is roughly **140+ tests** across these layers.

---

## Severity model

dbt tests run at one of two severities, chosen deliberately:

| Severity | Meaning | Used for |
|----------|---------|----------|
| **error** (default) | Build fails. The data cannot be trusted. | Hard invariants: unique keys, no negative prices, delivery never before purchase, revenue reconciliation, referential integrity. |
| **warn** | Build succeeds but flags the issue for review. | Known data quirks and soft thresholds where some deviation is expected but a spike should be investigated. |

The principle: **error** for things that must never be true, **warn** for
things that are usually fine but worth watching.

---

## Types of tests in use

### Generic tests (dbt built-in)
`unique`, `not_null`, `accepted_values`, and `relationships`, applied across
sources, staging, and marts. These are the bulk of the coverage.

### dbt_utils package tests
- `dbt_utils.unique_combination_of_columns` -- enforces the composite grain of `stg_order_items` and `fact_order_items` (`order_id` + `order_item_id`).
- `dbt_utils.accepted_range` -- bounds numeric columns (prices >= 0, review_score 1-5, n_items >= 0).
- `dbt_utils.expression_is_true` -- asserts `days_late >= 0` wherever it is populated.

### Singular tests (custom SQL, one assertion each)
Located in `tests/`:

| Test | Rule enforced |
|------|---------------|
| `assert_no_negative_amounts` | No item has a negative price or freight. |
| `assert_delivery_after_purchase` | No order is delivered before it was purchased. |
| `assert_fact_orders_grain_preserved` | `fact_orders` has exactly one row per `stg_orders` row (no join fan-out or drop). |
| `assert_item_revenue_reconciles` | Total item revenue is identical in `fact_order_items` and `fact_orders` (within 1 cent). |

These four are configured with `store_failures=true`, so any failing rows are
written to a `dq_failures` schema for inspection rather than just reported as a
count. This is how you debug a failing test in practice.

### Custom generic test
`proportion_not_null` (in `tests/generic/`) is a reusable test we authored.
The built-in `not_null` demands 100% completeness; this one asserts a column is
non-null *at least* some proportion of the time, for columns where partial
nulls are expected but a sudden spike signals a problem. It is applied to
`order_delivered_customer_date` at a 90% threshold (warn level), since ~3% of
orders are legitimately undelivered but a large jump would indicate a
delivery-feed issue.

---

## Known data quality issues (deliberately accepted)

These were surfaced during Phase 2 profiling and are handled rather than
treated as build-breaking errors:

| Issue | Volume | Handling |
|-------|--------|----------|
| `review_id` not unique in raw | ~814 dup IDs | Reviews deduplicated to one row per order in staging; `order_id` uniqueness enforced downstream. |
| `payment_type = 'not_defined'` | 3 rows | Included in source `accepted_values` (warn) so it is tracked; normalized to NULL in staging. |
| 1 order has no payment record | 1 row | Tolerated; `total_payment_value` is simply NULL for it. |
| ~610 products lack a category | 1.9% | Coalesced to `'uncategorized'` so they still appear in category reports. |
| ~2,965 orders have no delivery date | 3.0% | Expected (canceled/undelivered); flagged via the `delivery_status = 'not_delivered'` value and the proportion test. |

Documenting accepted issues is as important as catching unacceptable ones: it
shows the deviations are understood and intentional, not overlooked.

---

## Source freshness (intentionally not configured)

dbt supports source freshness checks (warn/error if data hasn't been updated
within an expected window). This project does **not** configure them, because
the Olist dataset is a static historical export (Sep 2016 - Oct 2018) with no
ongoing loads. In a production pipeline with live data, you would add a
`loaded_at` column during ingestion and a `freshness` block to each source so
stale data triggers an alert. The omission here is a deliberate fit to a static
dataset, not an oversight.

---

## Running the tests

```bash
# Run everything (models + tests)
dbt build

# Run only tests
dbt test

# Run tests for one model
dbt test --select fact_orders

# Run only the singular business-rule tests
dbt test --select test_type:singular

# After a failure, inspect the stored failing rows
#   (singular tests write to the dq_failures schema)
```

In a CI pipeline (Phase 9), `dbt build` runs on every pull request, so no
change merges unless all error-severity tests pass.