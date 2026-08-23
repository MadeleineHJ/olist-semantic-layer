{#
  not_null demands 100%, but some columns are legitimately null some of
  the time (e.g. a delivery date on an order that's still in transit).
  This checks the non-null rate stays above `at_least` instead of
  failing on every single null.

  usage:
    - proportion_not_null:
        at_least: 0.90
        config:
          severity: warn
#}

{% test proportion_not_null(model, column_name, at_least) %}

with validation as (

    select
        count(*)                  as total_rows,
        count({{ column_name }})  as non_null_rows
    from {{ model }}

),

evaluation as (

    select
        total_rows,
        non_null_rows,
        case
            when total_rows = 0 then 0
            else non_null_rows::float / total_rows
        end as non_null_proportion
    from validation

)

select *
from evaluation
where non_null_proportion < {{ at_least }}

{% endtest %}