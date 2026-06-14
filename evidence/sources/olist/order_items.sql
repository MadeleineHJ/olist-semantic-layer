select
    order_id,
    order_item_id,
    customer_key,
    product_key,
    seller_key,
    order_date_key,
    delivery_status,
    is_delivered,
    price,
    freight_value,
    gross_item_value
from main_marts.fact_order_items