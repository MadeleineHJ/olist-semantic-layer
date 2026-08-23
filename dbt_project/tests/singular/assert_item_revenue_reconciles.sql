{{ config(store_failures=true, schema='dq_failures') }}

-- item revenue should total the same whether it's summed from
-- fact_order_items or fact_orders. if it doesn't, the aggregation in
-- int_items_per_order is wrong. 1-cent tolerance for float rounding.

with items_grain as (
    select sum(price) as total_revenue
    from {{ ref('fact_order_items') }}
),

orders_grain as (
    select sum(total_item_price) as total_revenue
    from {{ ref('fact_orders') }}
)

select
    i.total_revenue as items_fact_revenue,
    o.total_revenue as orders_fact_revenue,
    abs(i.total_revenue - o.total_revenue) as difference
from items_grain i
cross join orders_grain o
where abs(i.total_revenue - o.total_revenue) > 0.01