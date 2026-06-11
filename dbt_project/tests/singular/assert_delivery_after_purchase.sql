{{ config(store_failures=true, schema='dq_failures') }}

-- Business rule: an order cannot be delivered before it was purchased.
-- If this fails, either the source timestamps are corrupt or our
-- delivery_days / days_late calculations will produce nonsense.
-- FAILS if any offending rows are returned.

select
    order_id,
    order_purchase_timestamp,
    order_delivered_customer_date
from {{ ref('stg_orders') }}
where order_delivered_customer_date is not null
  and order_delivered_customer_date < order_purchase_timestamp