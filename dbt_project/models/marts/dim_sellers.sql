-- one row per seller.

with sellers as (

    select * from {{ ref('stg_sellers') }}

)

select
    seller_id  as seller_key,
    seller_id,

    seller_city,
    seller_state,
    seller_zip_code_prefix,
    is_southeast_region

from sellers