# data/ (local only, gitignored)

Everything in this folder except this README is ignored by Git.

```
data/
  raw/olist/snapshot_date=YYYY-MM-DD/   # immutable Kaggle download + _manifest.json
  landing/olist/load_date=YYYY-MM-DD/   # (later) daily replay batches pushed to Snowflake
```

Rebuild it at any time with `python -m olist_ingest.download`.
