-- ============================================================================
-- int_payments_per_order
-- ----------------------------------------------------------------------------
-- Collapses one-row-per-payment-method into one-row-per-order so it can be
-- safely joined to fact_orders without exploding row counts.
-- Surfaces split-tender signals (n_payment_methods, has_voucher) and the
-- primary payment type (defined as the highest-value method on the order).
-- ============================================================================

with payments as (

    select * from {{ ref('stg_order_payments') }}

),

primary_payment as (

    -- Pick the highest-value payment row as the "primary" method
    select
        order_id,
        payment_type as primary_payment_type
    from payments
    qualify row_number() over (
        partition by order_id
        order by payment_value desc
    ) = 1

),

aggregated as (

    select
        order_id,
        sum(payment_value)                  as total_payment_value,
        count(*)                            as n_payment_rows,
        count(distinct payment_type)        as n_payment_methods,
        max(payment_installments)           as max_installments,
        bool_or(payment_type = 'voucher')   as has_voucher
    from payments
    group by order_id

)

select
    a.order_id,
    a.total_payment_value,
    a.n_payment_rows,
    a.n_payment_methods,
    a.max_installments,
    a.has_voucher,
    pp.primary_payment_type
from aggregated a
left join primary_payment pp using (order_id)