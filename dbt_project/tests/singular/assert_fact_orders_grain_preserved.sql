{{ config(store_failures=true, schema='dq_failures') }}

-- Business rule: fact_orders must have exactly one row per order in
-- stg_orders. The LEFT JOINs to items, payments, and reviews should
-- enrich orders, never multiply or drop them. If the row counts differ,
-- a join fan-out or filter bug has been introduced.
-- FAILS if the counts do not match.

with fact_count as (
    select count(*) as n_rows from {{ ref('fact_orders') }}
),

staging_count as (
    select count(*) as n_rows from {{ ref('stg_orders') }}
)

select
    f.n_rows as fact_orders_rows,
    s.n_rows as stg_orders_rows
from fact_count f
cross join staging_count s
where f.n_rows != s.n_rows