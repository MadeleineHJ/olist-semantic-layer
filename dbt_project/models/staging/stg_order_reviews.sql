-- ============================================================================
-- stg_order_reviews
-- ----------------------------------------------------------------------------
-- Grain: one row per order_id.
-- Source has 99,224 rows for 98,673 distinct orders -- 547 orders have
-- multiple reviews. We keep the most recent review per order.
-- This is data-cleaning, not business logic, so it lives in staging.
-- ============================================================================

with source as (

    select * from {{ source('olist_raw', 'order_reviews') }}

),

renamed as (

    select
        review_id,
        order_id,
        review_score,

        case when review_comment_title   is not null then true else false end as has_title,
        case when review_comment_message is not null then true else false end as has_comment,

        review_comment_title,
        review_comment_message,
        review_creation_date,
        review_answer_timestamp,

        -- derived: hours from review submission to response
        date_diff('hour', review_creation_date, review_answer_timestamp)
            as response_time_hours

    from source

),

deduplicated as (

    -- Keep the latest review per order. ROW_NUMBER + QUALIFY is the
    -- idiomatic pattern for "pick one row per group" in DuckDB.
    select *
    from renamed
    qualify row_number() over (
        partition by order_id
        order by review_creation_date desc
    ) = 1

)

select * from deduplicated