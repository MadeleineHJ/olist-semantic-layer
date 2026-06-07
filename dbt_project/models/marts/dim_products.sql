-- ============================================================================
-- dim_products
-- ----------------------------------------------------------------------------
-- Grain: one row per product.
-- Adds derived categorizations useful for dashboards:
--   - product_size_class: small / medium / large by weight
--   - listing_quality:    high / medium / low by photo count + description
-- ============================================================================

with products as (

    select * from {{ ref('stg_products') }}

)

select
    product_id  as product_key,
    product_id,

    -- category
    product_category,

    -- size classification (in grams)
    case
        when product_weight_g is null    then 'unknown'
        when product_weight_g < 500      then 'small'
        when product_weight_g < 5000     then 'medium'
        else                                  'large'
    end as product_size_class,

    -- listing quality based on photos + description length
    case
        when product_photos_qty is null              then 'unknown'
        when product_photos_qty >= 3
             and product_description_length > 500    then 'high'
        when product_photos_qty >= 1                 then 'medium'
        else                                              'low'
    end as listing_quality,

    -- physical attributes
    product_weight_g,
    product_volume_cm3,
    product_length_cm,
    product_height_cm,
    product_width_cm,

    -- listing detail
    product_photos_qty,
    product_name_length,
    product_description_length

from products