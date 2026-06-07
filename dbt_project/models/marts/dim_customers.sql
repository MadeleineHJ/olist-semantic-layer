-- ============================================================================
-- dim_customers
-- ----------------------------------------------------------------------------
-- Grain: one row per customer_unique_id (the ACTUAL person).
-- Collapses the per-order customer_id rows from stg_customers.
--
-- See docs/phase2_findings.md section 2 for the customer_id vs
-- customer_unique_id distinction. This is the most important
-- modeling decision in the entire project.
-- ============================================================================

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