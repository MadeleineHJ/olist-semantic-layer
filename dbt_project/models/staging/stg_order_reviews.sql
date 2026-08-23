-- one row per order_id. Source has 99,224 rows for 98,673 distinct
-- orders -- 547 orders got reviewed more than once, we just keep
-- whichever review is newest.

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

    -- keep the latest review per order
    select *
    from renamed
    qualify row_number() over (
        partition by order_id
        order by review_creation_date desc
    ) = 1

)

select * from deduplicated