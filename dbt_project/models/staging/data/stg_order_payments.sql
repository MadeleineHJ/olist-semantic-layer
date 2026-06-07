-- ============================================================================
-- stg_order_payments
-- ----------------------------------------------------------------------------
-- Grain: one row per payment method used per order.
-- Kept at source grain here. Aggregation to one-row-per-order happens in
-- the intermediate/marts layer (so the raw payment-method detail stays
-- available for split-tender analysis).
-- ============================================================================

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