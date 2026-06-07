-- ============================================================================
-- stg_products
-- ----------------------------------------------------------------------------
-- Grain: one row per product_id.
-- Joins Portuguese -> English category translation.
-- Missing categories coalesced to 'uncategorized' so products without
-- metadata still appear in category-level reports.
-- ============================================================================

with products as (

    select * from {{ source('olist_raw', 'products') }}

),

translation as (

    select * from {{ source('olist_raw', 'product_category_translation') }}

),

joined as (

    select
        p.product_id,

        -- category: prefer English translation, fall back to original,
        -- then to 'uncategorized'
        coalesce(
            t.product_category_name_english,
            p.product_category_name,
            'uncategorized'
        ) as product_category,

        -- text metadata (raw fields typo'd 'lenght' in source -- fix here)
        p.product_name_lenght        as product_name_length,
        p.product_description_lenght as product_description_length,
        p.product_photos_qty,

        -- physical dimensions (cm, g)
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,

        -- derived: volume in cubic cm
        case
            when p.product_length_cm is not null
             and p.product_height_cm is not null
             and p.product_width_cm  is not null
            then p.product_length_cm * p.product_height_cm * p.product_width_cm
        end as product_volume_cm3

    from products p
    left join translation t
        on p.product_category_name = t.product_category_name

)

select * from joined