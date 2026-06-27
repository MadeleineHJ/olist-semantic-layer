# Olist Marketplace Analytics

[![CI](https://github.com/MadeleineHJ/olist-semantic-layer/actions/workflows/ci.yml/badge.svg)](https://github.com/MadeleineHJ/olist-semantic-layer/actions/workflows/ci.yml)

**Live dashboard:** [olist-marketplace-analytics.netlify.app](https://olist-marketplace-analytics.netlify.app)

End-to-end analytics engineering project on the Olist Brazilian e-commerce
dataset (~99,441 orders, Sep 2016 – Oct 2018). Demonstrates the full pipeline
from raw CSVs to a governed semantic layer and a deployed BI dashboard.

> **TL;DR**
>
> Late delivery is the single biggest driver of customer dissatisfaction on the
> Olist marketplace. On-time orders average **4.29 / 5** stars; late orders fall
> to **2.57**; undelivered orders to **1.76**. The 1.72-point drop from late
> delivery is the headline finding of the dataset and the story the dashboard
> argues end-to-end.

## Architecture

```mermaid
flowchart LR
    csv["9 raw CSVs<br/>Olist Kaggle"]
    raw["DuckDB<br/>raw schema"]
    stg["dbt staging<br/>8 models"]
    int["dbt intermediate<br/>2 models"]
    marts["dbt marts<br/>4 dims + 2 facts"]
    sem["MetricFlow<br/>11 governed metrics"]
    tests["dbt tests<br/>140+ checks"]
    dq[("dq_failures<br/>audit schema")]
    bi["Evidence.dev<br/>dashboard"]
    deploy["Netlify<br/>live URL"]

    csv -->|Python ingest| raw
    raw --> stg
    stg --> int
    int --> marts
    marts --> sem
    marts -.->|validate| tests
    tests -.->|store_failures| dq
    sem --> bi
    bi -->|npm run build| deploy

    classDef src fill:#f1efe8,stroke:#888780,color:#2c2c2a
    classDef warehouse fill:#e6f1fb,stroke:#185fa5,color:#042c53
    classDef transform fill:#e1f5ee,stroke:#0f6e56,color:#04342c
    classDef govern fill:#eeedfe,stroke:#534ab7,color:#26215c
    classDef quality fill:#faeeda,stroke:#854f0b,color:#412402

    class csv src
    class raw warehouse
    class stg,int,marts transform
    class sem,bi,deploy govern
    class tests,dq quality
```

## Tech stack

| Layer            | Tool                                           |
|------------------|------------------------------------------------|
| Warehouse        | DuckDB (local, zero-infrastructure)            |
| Transformation   | dbt with the dbt-duckdb adapter, dbt_utils     |
| Semantic layer   | MetricFlow                                     |
| Data quality     | dbt tests, store_failures, custom generic test |
| BI / dashboard   | Evidence.dev (DuckDB connector)                |
| Ingestion        | Python (duckdb + read_csv_auto)                |
| CI               | GitHub Actions (`dbt build` on every PR)        |

## Continuous integration

Every push to `main` and every pull request runs a GitHub Actions workflow
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) that:

1. Stages sample CSVs from `tests/fixtures/` into `raw_data/`
2. Loads them into a fresh DuckDB warehouse
3. Installs the dbt packages (`dbt deps`)
4. Compiles the dbt project (`dbt compile`)
5. Builds all models and runs all 140+ tests (`dbt build`)

The badge above turns green only when every model builds and every test passes.
Tests are run against committed sample data (`tests/fixtures/`, ~36 KB total)
rather than the full Olist dataset, which keeps CI runs under 3 minutes and
avoids shipping the 50 MB raw data with the repo.

## Project structure

```
olist-semantic-layer/
├── raw_data/                     # 9 CSVs (gitignored, not committed)
├── scripts/
│   ├── load_raw_data.py          # ingest CSVs into DuckDB raw schema
│   ├── verify_raw_data.py        # null profiling + FK integrity checks
│   └── profile_data.py           # 10-area systematic profiling
├── dbt_project/
│   ├── models/
│   │   ├── staging/              # 8 stg_* models (1:1 with sources)
│   │   ├── intermediate/         # 2 int_* models (per-order aggregations)
│   │   └── marts/                # 4 dims + 2 facts + semantic + metrics
│   ├── tests/                    # 4 singular + custom generic tests
│   └── packages.yml              # dbt_utils
├── evidence/                     # BI layer
│   ├── pages/index.md            # consolidated single-page dashboard
│   └── sources/olist/            # DuckDB source queries
├── tests/
│   └── fixtures/                 # sample CSVs (36KB) used by CI
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions: dbt build + tests on every PR
├── docs/
│   ├── phase2_findings.md        # data profiling decisions
│   ├── metrics_catalog.md        # governance artifact for the semantic layer
│   └── data_quality.md           # testing strategy
└── README.md
```

## Phase-by-phase summary

| Phase | Layer                | Deliverable                                                   |
|-------|----------------------|---------------------------------------------------------------|
| 1     | Ingestion            | DuckDB warehouse with 9 raw tables, FK-validated              |
| 2     | Profiling            | Grain decisions documented (customer_unique_id vs customer_id) |
| 3     | Staging              | 8 stg_* models with derived flags, dedup, normalization       |
| 4     | Marts                | dim_customers, dim_products, dim_sellers, dim_dates + 2 facts |
| 5     | Semantic layer       | 11 governed metrics formalizing Phase 2 ambiguities           |
| 6     | Data quality         | 140+ tests, store_failures schema, custom generic test        |
| 7     | BI                   | Evidence dashboard on the marts                               |

## Key engineering decisions

**Customer grain collapse.** Phase 2 profiling surfaced a 3,345-row gap between
`customer_id` (99,441 rows, per-order identity) and `customer_unique_id`
(96,096 rows, per-person identity). `dim_customers` is built at the
`customer_unique_id` grain because anything at the per-order grain would
double-count repeat customers. This decision flows through every downstream
metric.

**Why a semantic layer when the marts are correct.** The marts give clean
ingredients; the semantic layer gives one agreed recipe. Without it, three
analysts can each compute revenue three different ways from the same correct
table. MetricFlow definitions resolve that. See `docs/metrics_catalog.md`.

**store_failures for business-rule violations.** Singular dbt tests
(`assert_no_negative_amounts`, `assert_delivery_after_purchase`, etc.) are
configured with `store_failures=true` and routed to a dedicated
`main_dq_failures` schema. Data quality is auditable, not just pass/fail.

**Custom generic test (`proportion_not_null`).** dbt's built-in `not_null`
fails on a single null. Real-world columns often have legitimate sparsity
(e.g. `order_delivered_customer_date` is null when an order is in transit or
canceled). This custom test enforces a configurable threshold (e.g. 90%)
instead of binary pass/fail.

**No `fact_payments` table.** Payments are an order-process attribute, not
an independent business process (avg 1.045 payments per order, no own
dimensions). Payment data is folded into `fact_orders` via an intermediate
aggregation rather than creating a separate fact, which would have invited
fan-out bugs.

## Quickstart

Requires Python 3.10+ and Node.js 18+. Tested on Windows PowerShell.

**1. Load raw data**

```bash
pip install -r requirements.txt
python scripts/load_raw_data.py
python scripts/verify_raw_data.py
```

**2. Build dbt**

```bash
cd dbt_project
$env:DBT_PROFILES_DIR="."     # PowerShell; use export DBT_PROFILES_DIR=. on bash
dbt deps
dbt build
```

Expected: ~140+ PASS, 1 WARN (acceptable per the data quality doc), 0 ERROR.

**3. Query metrics**

```bash
mf list metrics
mf query --metrics revenue_net --group-by metric_time__month
mf query --metrics average_review_score --group-by order__delivery_status
```

**4. Launch dashboard**

```bash
cd evidence
npm install --legacy-peer-deps
npm run sources
npm run dev
```

Dashboard opens at http://localhost:3000.

## Documentation

- [`docs/phase2_findings.md`](docs/phase2_findings.md) — profiling and grain decisions
- [`docs/metrics_catalog.md`](docs/metrics_catalog.md) — the 11 governed metrics
- [`docs/data_quality.md`](docs/data_quality.md) — testing strategy and severity

## Skills demonstrated

- Dimensional modeling (Kimball-style star schema)
- dbt model layering (staging → intermediate → marts)
- Semantic-layer governance (MetricFlow)
- Data quality engineering (built-in + dbt_utils + custom tests + store_failures)
- SQL window functions, qualify deduplication, time-spine modeling
- BI-as-code (Evidence.dev with version-controlled dashboards)
- DuckDB for local analytics

## Data source

Olist Brazilian E-Commerce Public Dataset.
Licensed CC BY-NC-SA 4.0. See https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

## License

MIT for project code. Data is governed by its original CC BY-NC-SA 4.0 license.