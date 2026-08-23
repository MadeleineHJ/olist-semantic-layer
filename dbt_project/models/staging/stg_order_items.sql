-- one row per item, so an order with 3 items = 3 rows here.

with source as (

    select * from {{ source('olist_raw', 'order_items') }}

),

renamed as (

    select
        -- composite key
        order_id,
        order_item_id,

        -- relationships
        product_id,
        seller_id,

        -- timing
        shipping_limit_date,

        -- amounts (BRL)
        price,
        freight_value,

        -- derived: total amount paid for this line item
        price + freight_value as gross_item_value

    from source

)

select * from renamed