# Project status

_Updated at the end of every work session._

## Current phase: 0, scope and repository setup

### Done
- [x] Local repo initialised (`git init -b main`, no commits yet)
- [x] Repo skeleton: README, .gitignore, .env.example, pyproject.toml
- [x] Python venv `.venv` with kaggle 2.2.5, pandas 3.1.1, python-dotenv, ruff
- [x] `olist_ingest.download`: immutable dated snapshot, atomic write, manifest with hashes and row counts
- [x] `olist_ingest.profiling`: generates `docs/data_inventory.md`
- [x] ADR 0001 drafted: daily replay, stage + COPY, GitHub Actions orchestration

- [x] Kaggle token configured; snapshot `2026-11-25` downloaded (9 files)
- [x] Profiling run, `docs/data_inventory.md` generated

### Next
- [x] Findings reviewed; 12 decisions agreed in `docs/phase0_findings.md`
- [x] ADR 0001 accepted
- [x] MIT license added (code only; data keeps its own license)
- [x] First commit on `main`
- [ ] Create an empty GitHub repo, add the remote and push

## Decisions log
| Date | Decision | Where |
|---|---|---|
| 2026-11-25 | Monorepo: ingestion (Python) + transform (dbt) + infra + bi | README |
| 2026-11-25 | Raw data never committed; downloaded via Kaggle API into dated snapshots | download.py |
| 2026-11-25 | Phase 0 data decisions D1–D12 (review key, customer grain, revenue definition, KPI window...) | phase0_findings.md |
| 2026-11-25 | Daily feed simulated by an event-based replay; orchestrated by GitHub Actions | ADR 0001 (accepted) |
| 2026-11-25 | MIT license for code | LICENSE |

## Environment notes
- `dbt --version` = 2.0.11, which is **dbt Fusion** (Rust engine, dbt Core v2). Check Snowflake adapter auth before Phase 3.
- Kaggle auth: `KAGGLE_API_TOKEN` env var (confirmed in the kaggle 2.2.5 source); legacy `kaggle.json` also works.

## Open issues
- kaggle 2.2.5 imports `six` without declaring it; pinned `six` in pyproject.toml (fixed)
- Root cause of the 382 payment/item mismatches is still to be investigated (Phase 5)
