-- one row per payment method per order -- kept at source grain here on
-- purpose, aggregation to one-row-per-order happens in int_payments_per_order
-- so the split-tender detail isn't thrown away this early.

with source as (

    select * from {{ source('olist_raw', 'order_payments') }}

),

renamed as (

    select
        order_id,
        payment_sequential,

        -- normalize 'not_defined' to null so it surfaces cleanly
        case
            when payment_type = 'not_defined' then null
            else payment_type
        end as payment_type,

        payment_installments,
        payment_value

    from source

)

select * from renamed