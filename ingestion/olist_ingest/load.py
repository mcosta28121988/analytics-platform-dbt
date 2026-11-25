"""Load an Olist snapshot into OLIST_RAW.OLIST through an internal stage (PUT + COPY INTO).

    python -m olist_ingest.load                          # latest snapshot, all in-scope files
    python -m olist_ingest.load --only orders,sellers    # a subset of tables

Design (ADR 0001, ADR 0002):
- RAW is as delivered: every source column is VARCHAR, no business logic. Typing and
  cleaning happen in dbt staging, where they are tested and documented.
- Append-only, with load metadata on every row: _source_file, _file_row_number, _load_id,
  _load_date, _loaded_at. This traces any raw row back to the exact file and run that
  delivered it.
- Idempotent: COPY INTO remembers which staged files it already loaded into each table,
  so a rerun skips them instead of duplicating rows.
- Fail loudly: the CSV header is checked against the table before loading (COPY maps
  columns by position), and ON_ERROR = ABORT_STATEMENT rejects a bad file as a whole.
- Reconciled: rows in RAW per file are compared with the manifest row counts from Phase 0,
  written to OLIST_RAW.OLIST._LOAD_AUDIT and to docs/phase2_load_reconciliation.md.
  The exit code is 1 if anything does not reconcile.

The loader owns its objects (file format, stage, raw tables, audit table) and creates them
idempotently. Account-level objects (roles, warehouses, databases) stay in infra/snowflake,
run by admins. That mirrors a common split: the platform team provisions, the pipeline
manages what it writes.
"""

import argparse
import csv
import json
import re
import sys
import uuid
from datetime import UTC, datetime

from olist_ingest.config import DOCS_DIR, SOURCES, SourceFile, latest_snapshot_dir
from olist_ingest.snowflake_conn import connect

ROLE = "OLIST_LOADER"
WAREHOUSE = "OLIST_LOADING_WH"
SCHEMA = "OLIST_RAW.OLIST"
STAGE = f"{SCHEMA}.OLIST_LANDING"
FILE_FORMAT = f"{SCHEMA}.OLIST_CSV"
AUDIT_TABLE = f"{SCHEMA}._LOAD_AUDIT"
REPORT_PATH = DOCS_DIR / "phase2_load_reconciliation.md"

METADATA_COLUMNS = ["_SOURCE_FILE", "_FILE_ROW_NUMBER", "_LOAD_ID", "_LOAD_DATE", "_LOADED_AT"]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SETUP_SQL = [
    f"""create file format if not exists {FILE_FORMAT}
        type = csv
        skip_header = 1
        field_optionally_enclosed_by = '"'   -- review comments contain commas and line breaks
        empty_field_as_null = true           -- an empty field is a missing value
        skip_byte_order_mark = true          -- the translation file starts with a UTF-8 BOM
        encoding = 'UTF8'
        error_on_column_count_mismatch = true
        comment = 'Olist source CSVs, read as delivered'""",
    f"""create stage if not exists {STAGE}
        file_format = {FILE_FORMAT}
        comment = 'Landing zone for Olist files, partitioned by load_date='""",
    f"""create table if not exists {AUDIT_TABLE} (
        load_id          varchar   not null,
        load_date        date      not null,
        table_name       varchar   not null,
        source_file      varchar   not null,
        file_sha256      varchar,
        expected_rows    number,
        rows_loaded      number,   -- rows this run's COPY inserted (0 when skipped)
        rows_in_raw      number,   -- rows in the raw table that came from this file
        status           varchar   not null,
        started_at       timestamp_ntz,
        finished_at      timestamp_ntz,
        message          varchar
    ) comment = 'One row per file per load run: expected vs loaded row counts'""",
]


def read_header(path) -> list[str]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))
    bad = [c for c in header if not IDENTIFIER.match(c)]
    if bad:
        raise ValueError(f"{path.name}: column names are not plain identifiers: {bad}")
    return [c.upper() for c in header]


def table_columns(cur, table: str) -> list[str]:
    cur.execute(
        "select column_name from olist_raw.information_schema.columns "
        "where table_schema = 'OLIST' and table_name = %s order by ordinal_position",
        (table.upper(),),
    )
    return [r[0] for r in cur.fetchall()]


def ensure_table(cur, src: SourceFile, header: list[str]) -> None:
    """Create the raw table, or verify an existing one still matches the file header."""
    table = f"{SCHEMA}.{src.table.upper()}"
    existing = table_columns(cur, src.table)
    expected = header + METADATA_COLUMNS
    if not existing:
        cols = ",\n    ".join(f"{c} varchar" for c in header)
        cur.execute(
            f"""create table {table} (
    {cols},
    _source_file      varchar        not null,
    _file_row_number  number         not null,
    _load_id          varchar        not null,
    _load_date        date           not null,
    _loaded_at        timestamp_ntz  not null
) comment = '{src.description.replace("'", "''")} (raw, as delivered)'"""
        )
    elif existing != expected:
        raise RuntimeError(
            f"Schema drift in {table}: file columns {header} do not match the table "
            f"{existing[: -len(METADATA_COLUMNS)]}. Stop and review before loading."
        )


def copy_file(cur, src: SourceFile, header: list[str], stage_dir: str, staged_name: str,
              load_id: str, load_date: str) -> int:
    """COPY one staged file into its raw table. Returns rows loaded (0 if already loaded)."""
    positions = ", ".join(f"${i}" for i in range(1, len(header) + 1))
    columns = ", ".join(header + METADATA_COLUMNS)
    cur.execute(
        f"""copy into {SCHEMA}.{src.table.upper()} ({columns})
from (
    select {positions},
           metadata$filename, metadata$file_row_number,
           %s, %s::date, sysdate()
    from @{STAGE}/{stage_dir}/
)
files = ('{staged_name}')
file_format = (format_name = '{FILE_FORMAT}')
on_error = abort_statement""",
        (load_id, load_date),
    )
    desc = [d[0].lower() for d in cur.description]
    rows = [dict(zip(desc, r)) for r in cur.fetchall()]
    # A skipped (already loaded) file returns a single status row without rows_loaded.
    return sum(int(r.get("rows_loaded") or 0) for r in rows)


def rows_in_raw(cur, table: str, source_file: str) -> int:
    cur.execute(f"select count(*) from {SCHEMA}.{table.upper()} where _source_file = %s",
                (source_file,))
    return cur.fetchone()[0]


def write_report(results: list[dict], load_id: str, snapshot: str) -> None:
    lines = [
        "# Phase 2 load reconciliation",
        "",
        f"_Generated by `python -m olist_ingest.load`. Run `{load_id}`, snapshot `{snapshot}`._",
        "",
        ("Expected rows come from the Phase 0 manifest (parsed with a real CSV reader, so "
         "multi-line review comments count once). `rows_in_raw` counts every row in RAW that "
         "came from the file, across all runs, so a rerun must not change it."),
        "",
        "| Table | Source file | Expected | Loaded this run | In RAW | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['table_name']} | {r['source_file']} | {r['expected_rows']:,} | "
            f"{r['rows_loaded']:,} | {r['rows_in_raw']:,} | {r['status']} |"
        )
    total_ok = sum(r["status"] in ("LOADED", "ALREADY_LOADED") for r in results)
    lines += ["", f"**{total_ok} / {len(results)} files reconcile.**", ""]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated table names, e.g. orders,sellers")
    args = parser.parse_args()

    snapshot_dir = latest_snapshot_dir()
    load_date = snapshot_dir.name.split("=", 1)[1]
    stage_dir = f"load_date={load_date}"
    manifest = {f["filename"]: f for f in
                json.loads((snapshot_dir / "_manifest.json").read_text())["files"]}

    sources = [s for s in SOURCES if s.in_scope]
    if args.only:
        wanted = {t.strip() for t in args.only.split(",")}
        unknown = wanted - {s.table for s in sources}
        if unknown:
            parser.error(f"unknown or out-of-scope tables: {sorted(unknown)}")
        sources = [s for s in sources if s.table in wanted]

    load_id = str(uuid.uuid4())
    print(f"Load {load_id}: snapshot {load_date}, {len(sources)} file(s) -> {SCHEMA}")
    results = []

    with connect(role=ROLE, warehouse=WAREHOUSE) as conn, conn.cursor() as cur:
        for sql in SETUP_SQL:
            cur.execute(sql)

        for src in sources:
            started = datetime.now(UTC).replace(tzinfo=None)
            path = snapshot_dir / src.filename
            staged_name = src.filename + ".gz"
            source_file = f"{stage_dir}/{staged_name}"
            expected = manifest[src.filename]["row_count"]
            result = {
                "load_id": load_id, "load_date": load_date, "table_name": src.table.upper(),
                "source_file": source_file, "file_sha256": manifest[src.filename]["sha256"],
                "expected_rows": expected, "rows_loaded": 0, "rows_in_raw": 0,
                "started_at": started, "message": None,
            }
            try:
                header = read_header(path)
                ensure_table(cur, src, header)
                # OVERWRITE = FALSE: a staged file is immutable once landed.
                cur.execute(f"put 'file://{path.as_posix()}' @{STAGE}/{stage_dir}/ "
                            "auto_compress = true overwrite = false")
                result["rows_loaded"] = copy_file(cur, src, header, stage_dir, staged_name,
                                                  load_id, load_date)
                result["rows_in_raw"] = rows_in_raw(cur, src.table, source_file)
                if result["rows_in_raw"] != expected:
                    result["status"] = "MISMATCH"
                elif result["rows_loaded"] == 0:
                    result["status"] = "ALREADY_LOADED"
                else:
                    result["status"] = "LOADED"
            # Record any failure in the audit table, keep going, and fail the run at the end.
            except Exception as e:  # noqa: BLE001
                result["status"] = "FAILED"
                result["message"] = str(e).splitlines()[0][:500]
            result["finished_at"] = datetime.now(UTC).replace(tzinfo=None)
            results.append(result)

            cur.execute(
                f"""insert into {AUDIT_TABLE} (load_id, load_date, table_name, source_file,
                    file_sha256, expected_rows, rows_loaded, rows_in_raw, status,
                    started_at, finished_at, message)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                tuple(result[k] for k in (
                    "load_id", "load_date", "table_name", "source_file", "file_sha256",
                    "expected_rows", "rows_loaded", "rows_in_raw", "status",
                    "started_at", "finished_at", "message")),
            )
            print(f"  {src.table:<22} expected {expected:>9,}  loaded {result['rows_loaded']:>9,}"
                  f"  in RAW {result['rows_in_raw']:>9,}  {result['status']}"
                  + (f"  ({result['message']})" if result["message"] else ""))

    write_report(results, load_id, load_date)
    print(f"Report: {REPORT_PATH.relative_to(DOCS_DIR.parent)}")
    ok = all(r["status"] in ("LOADED", "ALREADY_LOADED") for r in results)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
