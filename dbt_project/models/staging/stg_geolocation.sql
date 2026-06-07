-- ============================================================================
-- stg_geolocation
-- ----------------------------------------------------------------------------
-- Grain: one row per zip code prefix.
-- Raw geolocation has ~52 rows per zip code (multiple lat/lng samples).
-- Joining the raw table directly to customers/sellers would multiply rows.
-- We collapse to a centroid (avg lat/lng) and the modal city/state per zip.
-- ============================================================================

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