{{ config(store_failures=true, schema='dq_failures') }}

-- an order can't be delivered before it was purchased. if this fires,
-- either the source timestamps are broken or delivery_days/days_late
-- will be nonsense.

select
    order_id,
    order_purchase_timestamp,
    order_delivered_customer_date
from {{ ref('stg_orders') }}
where order_delivered_customer_date is not null
  and order_delivered_customer_date < order_purchase_timestamp