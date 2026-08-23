-- one row per order. Also derives the delivery fields (on_time/late/
-- days_late) that fact_orders and the satisfaction analysis both need.

with source as (

    select * from {{ source('olist_raw', 'orders') }}

),

renamed as (

    select
        -- identifiers
        order_id,
        customer_id,

        -- status
        order_status,
        case when order_status = 'delivered' then true else false end as is_delivered,
        case when order_status = 'canceled'  then true else false end as is_canceled,

        -- timestamps
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,

        -- derived: delivery performance
        case
            when order_delivered_customer_date is not null
            then date_diff('day', order_purchase_timestamp, order_delivered_customer_date)
        end as delivery_days,

        case
            when order_delivered_customer_date is null then false
            when order_delivered_customer_date <= order_estimated_delivery_date then true
            else false
        end as is_on_time,

        case
            when order_delivered_customer_date is null then null
            when order_delivered_customer_date <= order_estimated_delivery_date then 0
            else date_diff('day',
                           order_estimated_delivery_date,
                           order_delivered_customer_date)
        end as days_late,

        case
            when order_delivered_customer_date is null then 'not_delivered'
            when order_delivered_customer_date <= order_estimated_delivery_date then 'on_time'
            else 'late'
        end as delivery_status

    from source

)

select * from renamed