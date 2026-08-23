-- rolls item-grain up to order-grain (n_items, totals) so fact_orders
-- isn't re-aggregating raw items itself.

with items as (

    select * from {{ ref('stg_order_items') }}

)

select
    order_id,
    count(*)                                as n_items,
    count(distinct product_id)              as n_distinct_products,
    count(distinct seller_id)               as n_sellers,
    sum(price)                              as total_item_price,
    sum(freight_value)                      as total_freight_value,
    sum(gross_item_value)                   as total_gross_item_value,
    avg(price)                              as avg_item_price,
    case
        when count(distinct seller_id) > 1 then true
        else false
    end                                     as is_multi_seller
from items
group by order_id