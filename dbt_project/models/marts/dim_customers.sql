-- collapses stg_customers down to one row per real person
-- (customer_unique_id), not per order. See docs/phase2_findings.md #2
-- for why -- this is the grain decision everything downstream leans on.

with customers as (

    select * from {{ ref('stg_customers') }}

),

deduplicated as (

    select
        customer_unique_id,

        -- Modal (most common) location attributes across the person's orders
        mode(customer_city)              as customer_city,
        mode(customer_state)             as customer_state,
        mode(customer_zip_code_prefix)   as customer_zip_code_prefix,
        bool_or(is_southeast_region)     as is_southeast_region,

        -- How many distinct customer_id rows did this person generate?
        count(*)                         as n_customer_ids
    from customers
    group by customer_unique_id

)

select
    customer_unique_id  as customer_key,
    customer_unique_id,                  -- keep as natural-key alias
    customer_city,
    customer_state,
    customer_zip_code_prefix,
    is_southeast_region,
    n_customer_ids

from deduplicated