{#
    Custom generic test: proportion_not_null
    ----------------------------------------
    Asserts that at least `at_least` (0-1) of the rows in a column are non-null.

    Unlike the built-in `not_null` test (which demands 100%), this is for
    columns where SOME nulls are expected and acceptable, but a sudden spike
    in nulls signals a data quality problem.

    Example usage in a schema.yml:

        columns:
          - name: order_delivered_customer_date
            tests:
              - proportion_not_null:
                  at_least: 0.90
                  config:
                    severity: warn

    The test FAILS (returns rows) if the non-null proportion drops below
    the threshold.
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