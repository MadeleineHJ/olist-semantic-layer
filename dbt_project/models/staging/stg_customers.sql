-- ============================================================================
-- stg_customers
-- ----------------------------------------------------------------------------
-- Grain: one row per customer_id (per-order customer context, NOT per person).
-- Downstream dim_customers will collapse to customer_unique_id grain.
-- ============================================================================

with source as (

    select * from {{ source('olist_raw', 'customers') }}

),

renamed as (

    select
        -- identifiers
        customer_id,
        customer_unique_id,

        -- geographic attributes
        customer_zip_code_prefix,
        lower(trim(customer_city))  as customer_city,
        upper(trim(customer_state)) as customer_state,

        -- derived: Brazilian southeast region flag (top 4 states by volume)
        case
            when customer_state in ('SP', 'RJ', 'MG', 'ES') then true
            else false
        end as is_southeast_region

    from source

)

select * from renamed