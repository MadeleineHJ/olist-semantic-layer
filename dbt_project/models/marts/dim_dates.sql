-- standard date spine, generated for 2016-2019 to cover the Olist
-- period with a little buffer on either side.

with date_spine as (

    select
        cast(range as date) as date_day
    from range(
        date '2016-01-01',
        date '2019-01-01',
        interval '1 day'
    )

)

select
    date_day as date_key,
    date_day,

    -- year, quarter, month
    extract(year    from date_day)                  as year,
    extract(quarter from date_day)                  as quarter,
    extract(month   from date_day)                  as month_number,
    monthname(date_day)                             as month_name,
    strftime(date_day, '%Y-%m')                     as year_month,
    cast(date_trunc('month',   date_day) as date)   as month_start,
    cast(date_trunc('quarter', date_day) as date)   as quarter_start,
    cast(date_trunc('year',    date_day) as date)   as year_start,

    -- day-level attributes
    extract(day        from date_day) as day_of_month,
    extract(dayofweek  from date_day) as day_of_week_number,
    dayname(date_day)                 as day_name,
    extract(dayofyear  from date_day) as day_of_year,
    extract(week       from date_day) as week_of_year,

    -- flags
    case
        when extract(dayofweek from date_day) in (0, 6) then true
        else false
    end as is_weekend

from date_spine