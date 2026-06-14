# Olist Evidence BI Layer

Self-serve dashboards for the Olist marketplace, built with Evidence.dev.
Reads directly from the dbt marts in the local DuckDB warehouse.

## Pages
- `index.md` -- executive overview (KPIs, delivery-vs-satisfaction, revenue trend, geography)
- `delivery_performance.md` -- on-time rate, days-late distribution, score vs delivery speed
- `revenue_and_products.md` -- revenue by category (with filter) and payment mix

## Run locally

Requires Node.js 18+.

```bash
npm install --legacy-peer-deps
npm run sources    # extracts data from the warehouse into the BI layer
npm run dev        # serves the dashboard at http://localhost:3000
```

The DuckDB connection is in `sources/olist/connection.yaml` and points at
`../../../olist_warehouse.duckdb` (the warehouse in the project root). Build
the warehouse first by running the dbt project.