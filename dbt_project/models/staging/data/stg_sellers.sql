-- ============================================================================
-- stg_sellers
-- ----------------------------------------------------------------------------
-- Grain: one row per seller_id.
-- ============================================================================

with source as (

    select * from {{ source('olist_raw', 'sellers') }}

),

renamed as (

    select
        seller_id,
        seller_zip_code_prefix,
        lower(trim(seller_city))  as seller_city,
        upper(trim(seller_state)) as seller_state,

        case
            when seller_state in ('SP', 'RJ', 'MG', 'ES') then true
            else false
        end as is_southeast_region

    from source

)

select * from renamed