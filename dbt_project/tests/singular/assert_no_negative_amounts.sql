{{ config(store_failures=true, schema='dq_failures') }}

-- prices/freight should never be negative -- would silently corrupt
-- revenue if it slipped through.

select
    order_id,
    order_item_id,
    price,
    freight_value
from {{ ref('stg_order_items') }}
where price < 0
   or freight_value < 0