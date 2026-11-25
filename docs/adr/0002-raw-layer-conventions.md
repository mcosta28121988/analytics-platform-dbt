# ADR 0002: Raw layer conventions

- **Status:** Accepted (2026-11-26)
- **Builds on:** [ADR 0001](0001-daily-ingestion-and-orchestration.md) (stage + COPY INTO, append-only raw)

## Context

Phase 2 loads the Olist snapshot into `OLIST_RAW.OLIST`. ADR 0001 fixed the path
(internal stage → `COPY INTO`). This ADR fixes what raw tables look like, so every later
source and the daily replay follow the same rules.

## Decisions

| # | Decision | Why |
|---|---|---|
| R1 | **Every source column is `VARCHAR`.** Casting happens in dbt staging. | Raw is "as delivered". One malformed date can't abort a load, odd values (D8, D10) stay visible for tests instead of being coerced, and typing logic lives in one tested place. This is the same pattern Fivetran and Airbyte use for raw data. |
| R2 | **Table name = source entity** (`ORDERS`, `ORDER_ITEMS`, ...) in schema `OLIST`; column names exactly as in the file header, typos included (D12). | The schema already names the source system, so a prefix adds nothing. Renames are business decisions and belong in staging. |
| R3 | **Load metadata on every row:** `_SOURCE_FILE`, `_FILE_ROW_NUMBER`, `_LOAD_ID`, `_LOAD_DATE`, `_LOADED_AT` (UTC). | Any raw row can be traced to the exact file, line and run. Staging deduplicates on `_LOADED_AT` once the replay delivers updated orders. |
| R4 | **Empty CSV field = `NULL`;** no other value changes. | An empty field in these files means "missing". Phase 0 null counts were computed the same way, so the two can be reconciled. |
| R5 | **Header check before every load.** If the file's columns differ from the table, the file is not loaded. | COPY maps columns by position. Without this check, a reordered column would load silently into the wrong field. Schema changes need a reviewed migration. |
| R6 | **`ON_ERROR = ABORT_STATEMENT`.** | A partly loaded file is worse than a failed one: a bad file must fail loudly, never skip rows silently. |
| R7 | **Every file in every run gets a row in `_LOAD_AUDIT`** with expected (manifest) vs loaded vs in-raw counts and a status. The run fails unless every file is `LOADED` or `ALREADY_LOADED`. | This is the reconciliation evidence the guide asks for. It can be queried, so dbt can test it later (for example: the latest load succeeded). |
| R8 | **The loader owns its objects** (file format, stage, raw tables, audit table) and creates them idempotently. Roles, warehouses and databases stay in `infra/snowflake/`. | The platform team provisions the account; the pipeline manages what it writes. `OLIST_LOADER` already has `CREATE TABLE/STAGE/FILE FORMAT` on the schema and nothing more. |
| R9 | **`category_translation` is loaded as a raw source table** (amends ADR 0001). The dbt seed holds only our own additions (the 2 missing translations, D5). | It is a file delivered by the source. Keeping it in raw separates source data from our additions, and the seed stays small and clearly ours. |
| R10 | **`geolocation` is not loaded** (Phase 0 decision). | No spatial use case yet. The loader skips any source marked `in_scope=False`. |

## Consequences

- dbt staging must cast every column and handle bad values explicitly. That is
  intended: this is where data-quality rules become visible and tested.
- Reruns are safe. COPY keeps load history for each table, so an already-loaded file is
  skipped (`ALREADY_LOADED`), and `rows_in_raw` must stay equal to the expected count.
  Caveat: Snowflake keeps that load history for 64 days. A file restaged after that
  could load twice. For a re-delivery, the replay (Phase 8) uses new file names per
  load date.
- Rebuilding raw from scratch (for example, in a new trial account) is:
  run `infra/snowflake` 01–06, then `python -m olist_ingest.load`.
