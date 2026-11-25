"""Profile the latest Olist snapshot and write docs/data_inventory.md.

    python -m olist_ingest.profiling

Files are read as text (dtype=str) on purpose. This mirrors the raw layer: we look at
the values exactly as delivered and *infer* types, instead of letting pandas coerce
them silently. Empty strings count as nulls.
"""

import json
import sys
from datetime import UTC, datetime

import pandas as pd

from olist_ingest.config import DOCS_DIR, SOURCES, latest_snapshot_dir


def read_raw(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""],
                       encoding="utf-8-sig")


def infer_type(s: pd.Series) -> str:
    v = s.dropna()
    if v.empty:
        return "all null"
    num = pd.to_numeric(v, errors="coerce")
    if num.notna().all():
        return "integer" if (num % 1 == 0).all() else "decimal"
    ts = pd.to_datetime(v, errors="coerce", format="mixed")
    if ts.notna().all():
        return "timestamp"
    return "string"


def profile_columns(df: pd.DataFrame) -> list[dict]:
    rows = []
    for col in df.columns:
        s = df[col]
        t = infer_type(s)
        info = {"column": col, "type": t, "nulls": int(s.isna().sum()),
                "null_pct": round(100 * s.isna().mean(), 2), "distinct": int(s.nunique()),
                "min": "", "max": ""}
        if t in ("integer", "decimal"):
            n = pd.to_numeric(s, errors="coerce")
            info["min"], info["max"] = n.min(), n.max()
        elif t == "timestamp":
            ts = pd.to_datetime(s, errors="coerce", format="mixed")
            info["min"], info["max"] = ts.min(), ts.max()
        rows.append(info)
    return rows


def key_check(df: pd.DataFrame, key: list[str]) -> dict:
    if not key:
        return {"key": "-", "duplicate_rows": None, "null_keys": None}
    dup = int(df.duplicated(subset=key, keep=False).sum())
    nulls = int(df[key].isna().any(axis=1).sum())
    return {"key": " + ".join(key), "duplicate_rows": dup, "null_keys": nulls}


def cross_checks(t: dict[str, pd.DataFrame]) -> list[tuple[str, str, str]]:
    """Business-relevant integrity checks. Returns (check, result, why it matters)."""
    o, oi, c, p = t["orders"], t["order_items"], t["customers"], t["products"]
    s, pay, r, tr = t["sellers"], t["order_payments"], t["order_reviews"], t["category_translation"]
    out = []

    def orphans(child, ckey, parent, pkey):
        return int((~child[ckey].isin(parent[pkey])).sum())

    out += [
        ("order_items.order_id not in orders", f"{orphans(oi, 'order_id', o, 'order_id'):,}",
         "Orphan child rows break fct_order_items relationships"),
        ("order_items.product_id not in products", f"{orphans(oi, 'product_id', p, 'product_id'):,}",
         "Needs an 'unknown product' dimension member if > 0"),
        ("order_items.seller_id not in sellers", f"{orphans(oi, 'seller_id', s, 'seller_id'):,}",
         "Same, for sellers"),
        ("orders.customer_id not in customers", f"{orphans(o, 'customer_id', c, 'customer_id'):,}",
         "Same, for customers"),
        ("order_payments.order_id not in orders", f"{orphans(pay, 'order_id', o, 'order_id'):,}", ""),
        ("order_reviews.order_id not in orders", f"{orphans(r, 'order_id', o, 'order_id'):,}", ""),
        ("orders with no items", f"{int((~o['order_id'].isin(oi['order_id'])).sum()):,}",
         "These orders have no revenue at item grain; decide how fct_orders treats them"),
        ("orders with no payment", f"{int((~o['order_id'].isin(pay['order_id'])).sum()):,}", ""),
    ]

    # Grain / fanout risks
    items_per_order = oi.groupby("order_id").size()
    pays_per_order = pay.groupby("order_id").size()
    reviews_per_order = r.groupby("order_id").size()
    orders_per_review = r.groupby("review_id")["order_id"].nunique()
    out += [
        ("orders with > 1 item", f"{int((items_per_order > 1).sum()):,} (max {items_per_order.max()})",
         "Joining items to orders multiplies order-level measures"),
        ("orders with > 1 payment line", f"{int((pays_per_order > 1).sum()):,} (max {pays_per_order.max()})",
         "Aggregate payments to order grain before joining"),
        ("orders with > 1 review", f"{int((reviews_per_order > 1).sum()):,}",
         "Reviews are not 1:1 with orders"),
        ("review_ids linked to > 1 order", f"{int((orders_per_review > 1).sum()):,}",
         "review_id alone is not a valid primary key"),
    ]

    # Customer identity
    out.append((
        "customer_id vs customer_unique_id",
        f"{c['customer_id'].nunique():,} ids / {c['customer_unique_id'].nunique():,} unique people",
        "customer_id is per-order; repeat-purchase analysis must use customer_unique_id",
    ))

    # Category translation coverage
    cats = p["product_category_name"]
    untranslated = sorted(set(cats.dropna()) - set(tr["product_category_name"]))
    out += [
        ("products with null category", f"{int(cats.isna().sum()):,}", "Needs an explicit 'unknown' label"),
        ("categories without English translation", f"{len(untranslated)}: {', '.join(untranslated) or '-'}",
         "Handle in staging/dim_products, don't drop products"),
    ]

    # Lifecycle consistency
    ts = {col: pd.to_datetime(o[col], errors="coerce") for col in
          ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
           "order_delivered_customer_date", "order_estimated_delivery_date"]}
    delivered = o["order_status"].eq("delivered")
    out += [
        ("delivered orders missing delivered_customer_date",
         f"{int((delivered & ts['order_delivered_customer_date'].isna()).sum()):,}",
         "Can't compute delivery time; must be excluded and documented"),
        ("non-delivered orders WITH delivered_customer_date",
         f"{int((~delivered & ts['order_delivered_customer_date'].notna()).sum()):,}",
         "Status and timestamps disagree"),
        ("delivered to customer before purchase",
         f"{int((ts['order_delivered_customer_date'] < ts['order_purchase_timestamp']).sum()):,}", ""),
        ("handed to carrier before approval",
         f"{int((ts['order_delivered_carrier_date'] < ts['order_approved_at']).sum()):,}",
         "Data-entry issue; affects 'approval-to-carrier' duration"),
        ("delivered after estimated date (late)",
         f"{int((delivered & (ts['order_delivered_customer_date'].dt.normalize() > ts['order_estimated_delivery_date'])).sum()):,}",
         "Candidate late-delivery definition: delivered date > estimated date"),
        ("order_status distribution",
         ", ".join(f"{k}={v:,}" for k, v in o["order_status"].value_counts().items()), ""),
    ]

    # Payment vs item reconciliation
    item_total = (pd.to_numeric(oi["price"]) + pd.to_numeric(oi["freight_value"])).groupby(oi["order_id"]).sum()
    pay_total = pd.to_numeric(pay["payment_value"]).groupby(pay["order_id"]).sum()
    both = pd.concat([item_total.rename("items"), pay_total.rename("pay")], axis=1).dropna()
    diff = (both["pay"] - both["items"]).abs()
    out += [
        ("orders where payments != items + freight (> R$0.01)",
         f"{int((diff > 0.01).sum()):,} of {len(both):,} (max diff R${diff.max():,.2f})",
         "Investigate (vouchers, installment interest) before choosing the revenue definition"),
        ("payment_type distribution",
         ", ".join(f"{k}={v:,}" for k, v in pay["payment_type"].value_counts().items()), ""),
        ("payment lines with value <= 0",
         f"{int((pd.to_numeric(pay['payment_value']) <= 0).sum()):,}", ""),
        ("review_score distribution",
         ", ".join(f"{k}={v:,}" for k, v in r["review_score"].value_counts().sort_index().items()), ""),
    ]
    return out


def md_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols = list(rows[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in r.values()) + " |" for r in rows]
    return "\n".join(lines)


def main() -> int:
    snap = latest_snapshot_dir()
    manifest = json.loads((snap / "_manifest.json").read_text())
    print(f"Profiling {snap}")

    tables: dict[str, pd.DataFrame] = {}
    summary, sections = [], []
    for src in SOURCES:
        path = snap / src.filename
        if not path.exists():
            summary.append({"table": src.table, "file": src.filename, "rows": "MISSING"})
            continue
        df = read_raw(path)
        if src.in_scope:
            tables[src.table] = df
        kc = key_check(df, src.expected_key)
        summary.append({
            "table": src.table, "file": src.filename, "in_scope": src.in_scope,
            "rows": f"{len(df):,}", "columns": len(df.columns), "expected_key": kc["key"],
            "duplicate_key_rows": kc["duplicate_rows"], "null_key_rows": kc["null_keys"],
        })
        print(f"  {src.table:22} {len(df):>10,} rows")
        if src.in_scope:
            sections.append(f"### {src.table}\n\n{src.description}  \n`{src.filename}`\n\n"
                            + md_table(profile_columns(df)))

    checks = cross_checks(tables)
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    doc = [
        "# Olist data inventory (Phase 0 profiling)",
        "",
        (f"_Generated by `python -m olist_ingest.profiling` at {generated} from snapshot "
        f"`{manifest['snapshot_date']}` ({manifest['source_url']}). Do not edit by hand; "
        "write findings and decisions in `docs/phase0_findings.md`._"),
        "",
        "## Files and key uniqueness",
        "",
        md_table(summary),
        "",
        "## Integrity, grain and data-quality checks",
        "",
        md_table([{"check": a, "result": b, "why it matters": w} for a, b, w in checks]),
        "",
        "## Column profiles",
        "",
        "\n\n".join(sections),
        "",
    ]
    out = DOCS_DIR / "data_inventory.md"
    out.write_text("\n".join(doc), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
