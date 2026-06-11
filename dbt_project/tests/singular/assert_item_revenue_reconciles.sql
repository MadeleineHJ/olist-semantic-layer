{{ config(store_failures=true, schema='dq_failures') }}

-- Business rule: total item revenue must be identical whether computed
-- from the item-grain fact (fact_order_items) or the pre-aggregated
-- order-grain fact (fact_orders). If they diverge, the aggregation in
-- int_items_per_order is wrong and revenue metrics can't be trusted.
-- A 1-cent tolerance absorbs floating-point rounding.
-- FAILS if the totals differ by more than 0.01.

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