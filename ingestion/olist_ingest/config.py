"""Single source of truth for paths and the source-file registry.

The SOURCES registry describes each Olist file once. Profiling uses it today; the
Snowflake loader (Phase 2) and the daily replay will reuse it, so a new file or key
change is made in exactly one place.
"""

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_OLIST_DIR = DATA_DIR / "raw" / "olist"
DOCS_DIR = PROJECT_ROOT / "docs"

KAGGLE_DATASET = "olistbr/brazilian-ecommerce"


@dataclass(frozen=True)
class SourceFile:
    table: str                      # future raw table name (without prefix)
    filename: str
    expected_key: list[str]         # the key we *expect* to be unique; profiling verifies it
    timestamp_columns: list[str] = field(default_factory=list)
    in_scope: bool = True
    description: str = ""


SOURCES: list[SourceFile] = [
    SourceFile(
        "orders", "olist_orders_dataset.csv", ["order_id"],
        ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
         "order_delivered_customer_date", "order_estimated_delivery_date"],
        description="Order header and lifecycle timestamps",
    ),
    SourceFile(
        "order_items", "olist_order_items_dataset.csv", ["order_id", "order_item_id"],
        ["shipping_limit_date"],
        description="One row per item in an order: product, seller, price, freight",
    ),
    SourceFile(
        "customers", "olist_customers_dataset.csv", ["customer_id"],
        description="Customer per order (customer_id) and real person (customer_unique_id)",
    ),
    SourceFile(
        "products", "olist_products_dataset.csv", ["product_id"],
        description="Product attributes and Portuguese category",
    ),
    SourceFile(
        "sellers", "olist_sellers_dataset.csv", ["seller_id"],
        description="Seller location",
    ),
    SourceFile(
        "order_payments", "olist_order_payments_dataset.csv", ["order_id", "payment_sequential"],
        description="Payment lines: type, installments, value",
    ),
    SourceFile(
        "order_reviews", "olist_order_reviews_dataset.csv", ["review_id"],
        ["review_creation_date", "review_answer_timestamp"],
        description="Customer review score and comments",
    ),
    SourceFile(
        "category_translation", "product_category_name_translation.csv",
        ["product_category_name"],
        description="Portuguese -> English category names",
    ),
    SourceFile(
        "geolocation", "olist_geolocation_dataset.csv", [],
        in_scope=False,
        description="Zip-prefix lat/long (deferred until a spatial use case exists)",
    ),
]


def latest_snapshot_dir() -> Path:
    """Return the most recent data/raw/olist/snapshot_date=... folder."""
    snapshots = sorted(p for p in RAW_OLIST_DIR.glob("snapshot_date=*") if p.is_dir())
    if not snapshots:
        raise FileNotFoundError(
            f"No snapshot in {RAW_OLIST_DIR}. Run `python -m olist_ingest.download` first."
        )
    return snapshots[-1]
