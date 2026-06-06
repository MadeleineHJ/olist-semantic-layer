# Olist Semantic Layer Project

A semantic-layer and self-serve BI project built on the Olist Brazilian E-Commerce dataset.
Demonstrates dimensional modeling, governed metrics definitions, and analytics delivery
using dbt, DuckDB, and Evidence.dev / Metabase.

## Project Structure

```
olist-semantic-layer/
├── raw_data/               # Place Olist CSV files here (gitignored)
├── scripts/
│   ├── load_raw_data.py    # Phase 1: Load CSVs into DuckDB raw schema
│   └── verify_raw_data.py  # Phase 1: Profile and validate raw data
├── dbt_project/            # Phase 3+: dbt models, tests, metrics
├── docs/                   # Metrics catalog, architecture diagram
├── olist_warehouse.duckdb  # DuckDB database (gitignored, generated)
├── requirements.txt
├── .gitignore
└── README.md
```

## Quick Start

### Phase 1: Load Raw Data

1. **Download the dataset** from Kaggle:
   https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

2. **Unzip** and place all 9 CSV files into the `raw_data/` directory:
   - `olist_customers_dataset.csv`
   - `olist_geolocation_dataset.csv`
   - `olist_order_items_dataset.csv`
   - `olist_order_payments_dataset.csv`
   - `olist_order_reviews_dataset.csv`
   - `olist_orders_dataset.csv`
   - `olist_products_dataset.csv`
   - `olist_sellers_dataset.csv`
   - `product_category_name_translation.csv`

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Load the data:**
   ```bash
   python scripts/load_raw_data.py
   ```

5. **Verify the load:**
   ```bash
   python scripts/verify_raw_data.py
   ```

   This prints row counts, column types, null percentages (flagging any
   column over 10%), and checks that foreign-key relationships between
   tables are intact.

## Tech Stack

| Layer          | Tool                |
|----------------|---------------------|
| Warehouse      | DuckDB              |
| Transformation | dbt (dbt-duckdb)    |
| Metrics Layer  | MetricFlow / Cube   |
| BI / Delivery  | Evidence.dev        |
| Language       | Python, SQL         |