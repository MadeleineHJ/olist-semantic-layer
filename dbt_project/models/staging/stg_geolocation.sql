-- raw geolocation has ~52 rows per zip (multiple lat/lng pings), so this
-- collapses to one row per zip -- centroid + most common city/state.
-- don't join the raw table anywhere else, it'll multiply rows.

with source as (

    select * from {{ source('olist_raw', 'geolocation') }}

),

aggregated as (

    select
        geolocation_zip_code_prefix as zip_code_prefix,

        -- centroid coordinates
        round(avg(geolocation_lat), 6) as latitude,
        round(avg(geolocation_lng), 6) as longitude,

        -- modal (most common) city/state for the zip
        mode(lower(trim(geolocation_city)))  as city,
        mode(upper(trim(geolocation_state))) as state,

        -- how many raw samples contributed (data quality signal)
        count(*) as n_samples

    from source
    group by 1

)

select * from aggregated