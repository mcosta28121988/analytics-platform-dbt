# Project status

_Updated at the end of every work session._

## Current phase: 2, raw ingestion (branch `feature/phase-2-raw-ingestion`)

### Phase 2: loaded and verified, awaiting commit/PR
- [x] Ingestion method chosen and documented: internal stage + PUT + COPY INTO (ADR 0001), raw conventions in ADR 0002
- [x] `olist_ingest.load`: header/schema-drift check, PUT, COPY with load metadata, `_LOAD_AUDIT`, markdown report
- [x] 8 files loaded into `OLIST_RAW.OLIST` (geolocation deferred); **8/8 reconcile** with the manifest, see `docs/phase2_load_reconciliation.md`
- [x] Rerun is idempotent: an already-loaded file is reported `ALREADY_LOADED`, RAW count unchanged
- [x] Spot checks match Phase 0 profiling (leading-zero zips 23,995; null categories 610; null delivery dates 2,965; null approvals 160; non-null review messages 40,977; multi-line comments preserved; BOM not leaked)
- [x] `OLIST_TRANSFORMER_DEV` can read the new raw tables (future grants work)
- [ ] Commit, PR into main (after the Phase 1 PR is merged), merge

### Phase 1: complete (2026-11-26), PR open
- [x] Infrastructure SQL in `infra/snowflake/` (roles, warehouses, databases, grants, users, resource monitor, verify, teardown)
- [x] `olist_ingest.snowflake_conn`: key-pair connection + privilege smoke test
- [x] snowflake-connector-python 5.2.0 added
- [x] Generate key pair for OLIST_SVC_DEV (outside repo, `%USERPROFILE%\.snowflake\keys\`, encrypted PKCS#8)
- [x] Run scripts 01 → 06 in the trial account; run 07_verify
- [x] Fill SNOWFLAKE_* in `.env`; `python -m olist_ingest.snowflake_conn` succeeds (2026-11-26)
- [x] Least-privilege check: TRANSFORMER_DEV can build in OLIST_ANALYTICS_DEV, is denied on OLIST_ANALYTICS (prod) and on writes to OLIST_RAW
- [ ] Commit, PR into main, merge

### Phase 0: complete (2026-11-25)
- Repo skeleton, MIT license, pushed to https://github.com/mcosta28121988/analytics-platform-dbt
- Kaggle snapshot `2026-11-25` downloaded; profiling in `docs/data_inventory.md`
- 12 data decisions in `docs/phase0_findings.md`; ADR 0001 accepted

## Decisions log
| Date | Decision | Where |
|---|---|---|
| 2026-11-25 | Monorepo: ingestion (Python) + transform (dbt) + infra + bi | README |
| 2026-11-25 | Raw data never committed; downloaded via Kaggle API into dated snapshots | download.py |
| 2026-11-25 | Phase 0 data decisions D1–D12 (review key, customer grain, revenue definition, KPI window...) | phase0_findings.md |
| 2026-11-25 | Daily feed simulated by an event-based replay; orchestrated by GitHub Actions | ADR 0001 (accepted) |
| 2026-11-25 | MIT license for code | LICENSE |
| 2026-11-25 | Existing Snowflake **trial** account; all objects prefixed `OLIST_`; infra as idempotent SQL so it can be rebuilt when the trial expires | infra/snowflake |
| 2026-11-25 | Separate prod (`OLIST_ANALYTICS`) and dev/CI (`OLIST_ANALYTICS_DEV`, transient) databases; dev roles have no prod access | 03_databases.sql |
| 2026-11-25 | 4 workload roles (loader, transformer dev/prod, reporter); BI table access via dbt `grants` only | 01, 04 |
| 2026-11-25 | Service user + key-pair (JWT) auth; prod service user deferred to Phase 10 | 05_users.sql |
| 2026-11-25 | 3 XS warehouses, auto-suspend 60 s, statement timeouts; 10-credit monthly resource monitor | 02, 06 |
| 2026-11-26 | Raw columns all VARCHAR; load metadata on every row; header check + ON_ERROR=ABORT | ADR 0002 |
| 2026-11-26 | category_translation loaded as raw (amends ADR 0001); dbt seed holds only our 2 added translations | ADR 0002 R9 |
| 2026-11-26 | Reconciliation persisted in `OLIST_RAW.OLIST._LOAD_AUDIT` + committed markdown report | ADR 0002 R7 |
| 2026-11-26 | Loader owns its objects (file format, stage, tables); account objects stay in infra SQL | ADR 0002 R8 |

## Environment notes
- `dbt --version` = 2.0.11, which is **dbt Fusion** (Rust engine, dbt Core v2). Check Snowflake adapter auth before Phase 3.
- Kaggle auth: `KAGGLE_API_TOKEN` env var (confirmed in the kaggle 2.2.5 source); legacy `kaggle.json` also works.
- OpenSSL 3.2.4 ships with Git for Windows: `C:\Program Files\Git\usr\bin\openssl.exe`.
- Snowflake trial: expires after 30 days or when free credits run out. Rebuild with scripts 01–06.

## Open issues
- kaggle 2.2.5 imports `six` without declaring it; pinned `six` in pyproject.toml (fixed)
- Key-pair gotcha (2026-11-26): an encrypted key with a wrong/missing passphrase surfaces as "Authentication failed. Unspecified"; verify locally by loading the key with `cryptography` first
- COPY load history lasts 64 days; a file restaged after that would load twice. The Phase 8 replay must use unique file names per load date (ADR 0002)
- Root cause of the 382 payment/item mismatches is still to be investigated (Phase 5)
