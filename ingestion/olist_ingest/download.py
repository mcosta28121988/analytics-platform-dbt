"""Download an immutable, dated snapshot of the Olist dataset from Kaggle.

    python -m olist_ingest.download            # skip if today's snapshot exists
    python -m olist_ingest.download --force    # re-download today's snapshot

Design choices (production patterns, at portfolio scale):
- Immutable snapshots: each run writes data/raw/olist/snapshot_date=YYYY-MM-DD/ and never
  edits an older one, so any downstream result can be traced to the exact files used.
- Atomic write: download to a ".partial" folder and rename only on success, so a failed
  run never leaves a half-written snapshot that looks complete.
- Manifest: _manifest.json records the file hashes and row counts that Phase 2
  reconciles Snowflake against.
"""

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

from olist_ingest.config import KAGGLE_DATASET, PROJECT_ROOT, RAW_OLIST_DIR


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_csv_rows(path) -> int:
    """Count data rows with a real CSV parser.

    Line counts are wrong for this dataset: review comments contain line breaks
    inside quoted fields, so a single record can span several lines.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download today's snapshot")
    args = parser.parse_args()

    # Load KAGGLE_* variables from .env before importing kaggle, which authenticates on import.
    load_dotenv(PROJECT_ROOT / ".env")
    from kaggle.api.kaggle_api_extended import KaggleApi

    snapshot_date = datetime.now(UTC).date().isoformat()
    snapshot_dir = RAW_OLIST_DIR / f"snapshot_date={snapshot_date}"
    partial_dir = snapshot_dir.with_name(snapshot_dir.name + ".partial")

    if snapshot_dir.exists() and not args.force:
        print(f"Snapshot already exists: {snapshot_dir} (use --force to replace)")
        return 0

    shutil.rmtree(partial_dir, ignore_errors=True)
    partial_dir.mkdir(parents=True)

    api = KaggleApi()
    api.authenticate()
    print(f"Downloading {KAGGLE_DATASET} -> {partial_dir}")
    api.dataset_download_files(KAGGLE_DATASET, path=str(partial_dir), unzip=True, quiet=False)

    files = []
    for path in sorted(partial_dir.glob("*.csv")):
        files.append({
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "row_count": count_csv_rows(path),
        })
        print(f"  {path.name:45} {files[-1]['row_count']:>10,} rows")

    manifest = {
        "dataset": KAGGLE_DATASET,
        "source_url": f"https://www.kaggle.com/datasets/{KAGGLE_DATASET}",
        "snapshot_date": snapshot_date,
        "downloaded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": files,
    }
    (partial_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    shutil.rmtree(snapshot_dir, ignore_errors=True)
    partial_dir.rename(snapshot_dir)
    print(f"Snapshot complete: {snapshot_dir} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
