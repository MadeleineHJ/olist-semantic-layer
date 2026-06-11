{{ config(store_failures=true, schema='dq_failures') }}

-- Business rule: prices and freight must never be negative.
-- A negative value would inflate or corrupt revenue metrics.
-- This test FAILS if any offending rows are returned.

select
    order_id,
    order_item_id,
    price,
    freight_value
from {{ ref('stg_order_items') }}
where price < 0
   or freight_value < 0