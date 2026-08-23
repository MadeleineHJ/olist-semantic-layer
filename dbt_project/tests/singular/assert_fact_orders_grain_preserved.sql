{{ config(store_failures=true, schema='dq_failures') }}

-- fact_orders should have exactly one row per stg_orders row -- the left
-- joins to items/payments/reviews are supposed to enrich, not multiply
-- or drop rows.

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