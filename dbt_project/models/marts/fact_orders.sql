-- one row per order (~99k). stg_orders is the spine; items, payments,
-- and the review all get left-joined on. This is what most of the
-- semantic layer and the dashboard actually query, not fact_order_items.

with orders as (

    select * from {{ ref('stg_orders') }}

),

customers as (

    select customer_id, customer_unique_id from {{ ref('stg_customers') }}

),

items as (

    select * from {{ ref('int_items_per_order') }}

),

payments as (

    select * from {{ ref('int_payments_per_order') }}

),

reviews as (

    select
        order_id,
        review_score,
        has_comment,
        review_creation_date
    from {{ ref('stg_order_reviews') }}

)

select
    -- primary key
    o.order_id,

    -- foreign keys to dimensions
    c.customer_unique_id                              as customer_key,
    cast(o.order_purchase_timestamp       as date)    as order_date_key,
    cast(o.order_delivered_customer_date  as date)    as delivered_date_key,
    cast(o.order_estimated_delivery_date  as date)    as estimated_delivery_date_key,

    -- order status attributes
    o.order_status,
    o.delivery_status,
    o.is_delivered,
    o.is_canceled,
    o.is_on_time,

    -- key timestamps (kept for time-of-day analysis)
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    -- delivery measures
    o.delivery_days,
    o.days_late,

    -- ITEM measures (from int_items_per_order)
    coalesce(i.n_items, 0)                            as n_items,
    coalesce(i.n_distinct_products, 0)                as n_distinct_products,
    coalesce(i.n_sellers, 0)                          as n_sellers,
    coalesce(i.total_item_price, 0)                   as total_item_price,
    coalesce(i.total_freight_value, 0)                as total_freight_value,
    coalesce(i.total_gross_item_value, 0)             as total_gross_item_value,
    i.avg_item_price,
    coalesce(i.is_multi_seller, false)                as is_multi_seller,

    -- PAYMENT measures (from int_payments_per_order)
    p.total_payment_value,
    p.n_payment_rows,
    p.n_payment_methods,
    p.max_installments,
    coalesce(p.has_voucher, false)                    as has_voucher,
    p.primary_payment_type,

    -- REVIEW attributes
    r.review_score,
    coalesce(r.has_comment, false)                    as has_review_comment,
    case when r.review_score is not null then true else false end as has_review

from orders o
left join customers c on o.customer_id = c.customer_id
left join items     i on o.order_id    = i.order_id
left join payments  p on o.order_id    = p.order_id
left join reviews   r on o.order_id    = r.order_id