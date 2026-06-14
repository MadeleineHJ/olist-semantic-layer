---
title: Olist Marketplace
description: Sales, delivery, and customer satisfaction across the Brazilian marketplace
---

<style>
    :global(.markdown) > p { margin-top: 0.25rem; margin-bottom: 0.5rem; font-size: 0.875rem; }
    :global(.markdown h2) { font-size: 1rem; font-weight: 600; margin: 1rem 0 0.25rem 0 !important; color: #1e3a8a; }

    /* Let Evidence Grid handle column counts (it does inline-block + percent widths).
       Only style the card appearance. */
    :global(div.grid) { margin-top: 0.5rem !important; }
    :global(div.grid > div) {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-radius: 8px !important;
        padding: 12px 14px !important;
        min-height: 130px !important;
        margin: 0 6px 8px 0 !important;
        box-sizing: border-box !important;
        vertical-align: top !important;
    }
    :global(div.grid > div:hover) { border-color: #1e3a8a !important; }
</style>

End-to-end view of the Brazilian marketplace. Data spans Sep 2016 – Oct 2018.

```sql kpis
select
    count(*)                                                         as total_orders,
    count(distinct customer_key)                                     as total_customers,
    sum(total_item_price) filter (where order_status = 'delivered') as net_revenue,
    sum(total_item_price) filter (where order_status = 'delivered')
        / nullif(count(*) filter (where is_delivered), 0)            as avg_order_value,
    100.0 * count(*) filter (where delivery_status = 'on_time')
        / nullif(count(*) filter (where is_delivered), 0)            as on_time_rate,
    avg(review_score)                                                as avg_review_score
from olist.orders
```

```sql review_by_delivery
select delivery_status, avg(review_score) as avg_review_score
from olist.orders where review_score is not null
group by delivery_status order by avg_review_score desc
```

```sql revenue_by_month
select
    date_trunc('month', order_purchase_timestamp) as order_month,
    sum(total_item_price) filter (where order_status = 'delivered') as net_revenue
from olist.orders group by 1 order by 1
```

```sql days_late_bucketed
with bucketed as (
    select
        case
            when days_late = 0 then '0 (same day)'
            when days_late between 1 and 3 then '1-3 days'
            when days_late between 4 and 7 then '4-7 days'
            when days_late between 8 and 14 then '8-14 days'
            when days_late between 15 and 30 then '15-30 days'
            else '30+ days'
        end as days_late_bucket,
        case
            when days_late = 0 then 1
            when days_late between 1 and 3 then 2
            when days_late between 4 and 7 then 3
            when days_late between 8 and 14 then 4
            when days_late between 15 and 30 then 5
            else 6
        end as bucket_order
    from olist.orders
    where delivery_status = 'late' and days_late is not null
)
select days_late_bucket, count(*) as orders
from bucketed group by days_late_bucket, bucket_order
order by bucket_order
```

```sql categories
select distinct product_category from olist.products order by product_category
```

```sql revenue_by_category
select p.product_category as product_category, sum(i.price) as revenue
from olist.order_items i
left join olist.products p on i.product_key = p.product_key
where i.is_delivered and p.product_category like '${inputs.category.value}'
group by 1 order by revenue desc limit 8
```

```sql payment_mix
select primary_payment_type as payment_method, count(*) as orders
from olist.orders where primary_payment_type is not null
group by 1 order by orders desc
```

<Grid cols=3>

<BigValue data={kpis} value=total_orders title="Orders" fmt=num0/>
<BigValue data={kpis} value=net_revenue title="Net Revenue" fmt='"R$ "#,##0'/>
<BigValue data={kpis} value=avg_order_value title="Avg Order Value" fmt='"R$ "#,##0'/>

<BigValue data={kpis} value=on_time_rate title="On-Time Delivery" fmt='0.0"%"'/>
<BigValue data={kpis} value=avg_review_score title="Avg Review" fmt='0.00'/>
<BigValue data={kpis} value=total_customers title="Customers" fmt=num0/>

</Grid>

## Delivery & satisfaction

<Grid cols=2>

<BarChart
    data={review_by_delivery}
    x=delivery_status y=avg_review_score
    fillColor="#1e3a8a"
    labels=true labelFmt='0.00' legend=false
    title="Review score by delivery"
    chartAreaHeight=130
    yAxisTitle=false xAxisTitle=false
/>

<AreaChart
    data={revenue_by_month}
    x=order_month y=net_revenue
    fillColor="#1e3a8a" lineColor="#1e3a8a" fillOpacity=0.15
    title="Revenue trend"
    chartAreaHeight=130
    yAxisTitle=false xAxisTitle=false
/>

</Grid>

<Grid cols=1>

<BarChart
    data={days_late_bucketed}
    x=days_late_bucket y=orders
    fillColor="#1e3a8a"
    labels=true labelFmt=num0
    title="Days late distribution"
    chartAreaHeight=160
    yAxisTitle=false xAxisTitle=false
    sort=false
/>

</Grid>

## Revenue & products

<Dropdown data={categories} name=category value=product_category title="Category">
    <DropdownOption value="%" valueLabel="All Categories"/>
</Dropdown>

<Grid cols=2>

<BarChart
    data={revenue_by_category}
    x=product_category y=revenue
    fillColor="#1e3a8a" swapXY=true
    title="Revenue by category"
    chartAreaHeight=130
    yAxisTitle=false xAxisTitle=false
/>

<BarChart
    data={payment_mix}
    x=payment_method y=orders
    fillColor="#1e3a8a" swapXY=true
    labels=true labelFmt=num0
    title="Payment methods"
    chartAreaHeight=130
    yAxisTitle=false xAxisTitle=false
/>

</Grid>

<Grid cols=1>

<BarChart
    data={revenue_by_category}
    x=product_category y=revenue
    fillColor="#1e3a8a"
    labels=true labelFmt='"R$ "#,##0'
    title="Category mix"
    chartAreaHeight=180
    yAxisTitle=false xAxisTitle=false
/>

</Grid>