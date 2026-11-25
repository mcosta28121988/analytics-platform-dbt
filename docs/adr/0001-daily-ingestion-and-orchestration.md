# ADR 0001: Daily ingestion and orchestration design

- **Status:** Accepted (2026-11-25)
- **Date:** 2026-11-25

## Context

The platform should behave like a real business pipeline where new source data arrives
every day. Olist, however, is a **static historical snapshot** (2016–2018) that Kaggle does
not update. We need to answer three questions:

1. How do we get "daily" data from a static dataset?
2. Where does the daily job run?
3. How do raw tables, dbt and reruns behave so a daily load is safe and cheap?

The project guide also says not to build production ingestion before the basic pipeline
works, so this design is staged.

## Decision

### 1. Simulate the source system with a daily "replay"

A small Python job plays the history forward one business day per run. For simulated day
`D` it emits the files a real order system would export that day:

| Entity | What is emitted on day D | Why |
|---|---|---|
| orders | every order with **any lifecycle event on D** (purchased, approved, handed to carrier, delivered), with later timestamps blanked and status set as of D | Orders *change* after creation. This creates real updates and late-arriving data. |
| order_items, order_payments | rows for orders purchased on D | Fixed at checkout |
| order_reviews | reviews with `review_creation_date` = D | Reviews arrive days after delivery |
| customers, products, sellers | rows first referenced on D | New dimension members appear over time |
| category_translation | dbt **seed** (static reference data) | Not a feed |

This gives incremental models, `merge` on a unique key, late-arriving facts and snapshots
(order-status history) a real reason to exist, instead of being demo features on a static table.

### 2. Land files in a stage; raw is append-only

```
replay job -> data/landing/olist/load_date=D/*.csv
           -> PUT  @RAW.OLIST_LANDING/load_date=D/
           -> COPY INTO RAW.OLIST_<TABLE>   (append-only)
```

Every raw table gets load metadata: `_source_file` (METADATA$FILENAME), `_file_row_number`,
`_load_date` and `_loaded_at`.

- **Idempotent reruns:** COPY INTO skips files it has already loaded (Snowflake keeps load
  metadata per table), so rerunning a failed day doesn't duplicate rows.
- **Raw keeps history:** an order can appear in several daily files. Staging picks the
  latest version per key (`qualify row_number() over (partition by order_id order by
  _loaded_at desc) = 1`), and a snapshot can keep the full status history.
- **In a real company** the stage would be an S3, ADLS or GCS bucket behind an external
  stage, filled by the source team or by a tool like Fivetran or Airbyte. Only the landing
  location changes; the COPY and dbt layers stay the same.

### 3. Transform with dbt against a prod target

`dbt build --target prod` runs models and tests in dependency order. Incremental models use
`merge` with a `unique_key` and a short lookback window (for example the last 3 days of
`_loaded_at`) to pick up late updates. Test failures stop the run, so bad data never reaches
the marts that Power BI reads.

### 4. Orchestrator: a scheduled GitHub Actions workflow

```
.github/workflows/daily_pipeline.yml   (cron, e.g. 06:00 UTC)
  1. replay day D          (python -m olist_ingest.replay)
  2. PUT + COPY INTO RAW   (python -m olist_ingest.load)
  3. dbt build --target prod
  4. publish dbt artifacts (run results, docs)
```

**Why:** it's free at this scale, lives in the repo next to the code, keeps every run's logs
visible (useful evidence for a portfolio), and handles one daily pipeline well.
Authentication uses a Snowflake **service user with key-pair auth**. The private key is
stored in GitHub Secrets and the user has a role that can only load RAW and build
ANALYTICS.

### Alternatives considered

| Option | When it's the right choice | Why not now |
|---|---|---|
| **Snowflake Tasks + dbt Projects on Snowflake** | Teams that want everything inside Snowflake, with no external runner | Strong candidate for a later iteration. The replay and download steps still need Python outside Snowflake. |
| **Airflow / Dagster / Prefect** | Many pipelines, cross-system dependencies, backfills, SLAs, alerting. The enterprise standard. | Hosting and operating it costs more than this project needs. |
| **Snowpipe (auto-ingest)** | Event-driven, near-real-time file arrival from cloud storage | A daily batch doesn't need it, and it requires cloud-bucket event notifications |
| **dbt Cloud scheduler** | Teams already on dbt Cloud | Runs transformations only (not ingestion), and is paid beyond the developer tier |
| **Windows Task Scheduler on this laptop** | Never for a "production" claim | Only runs while the PC is on; no audit trail |

We would move to Dagster or Airflow once there are several sources with dependencies
between them, or a need for backfill tooling.

## Rollout (staged, per the project guide)

| Phase | Ingestion capability |
|---|---|
| 0 | Download an immutable Kaggle snapshot and profile it |
| 2 | **One-time historical load** through the same stage + COPY path, from a manual run |
| 8 | Replay job + incremental models + order-status snapshot |
| 10 | GitHub Actions: CI on pull requests, then the scheduled daily pipeline |

## Consequences

- **Cost (estimate, to verify against real usage):** one XS warehouse at 1 credit/hour,
  billed per second with a 60-second minimum. A 2–5 minute daily run is about
  0.05–0.1 credits/day, or roughly 2–3 credits/month. Use `AUTO_SUSPEND = 60` and set a
  resource monitor in Phase 1.
- Raw grows with every daily file (an append-only log). That's acceptable at this volume
  and is the cost of being able to rebuild anything from raw.
- The replay is simulation code; the README must say clearly that the daily feed is
  simulated.
