-- item grain (~112k rows) -- use this for product/seller-level analysis.
-- For order-level questions, fact_orders is the one you want instead.

with items as (

    select * from {{ ref('stg_order_items') }}

),

orders as (

    select * from {{ ref('stg_orders') }}

),

customers as (

    select customer_id, customer_unique_id from {{ ref('stg_customers') }}

)

select
    -- composite degenerate dimension
    i.order_id,
    i.order_item_id,

    -- foreign keys to dimensions
    c.customer_unique_id                          as customer_key,
    i.product_id                                  as product_key,
    i.seller_id                                   as seller_key,
    cast(o.order_purchase_timestamp as date)      as order_date_key,

    -- order context (degenerate dimensions for filtering)
    o.order_status,
    o.delivery_status,
    o.is_delivered,
    o.is_canceled,
    o.is_on_time,

    -- timestamps
    o.order_purchase_timestamp,
    i.shipping_limit_date,

    -- measures (BRL)
    i.price,
    i.freight_value,
    i.gross_item_value

from items i
left join orders    o on i.order_id    = o.order_id
left join customers c on o.customer_id = c.customer_id