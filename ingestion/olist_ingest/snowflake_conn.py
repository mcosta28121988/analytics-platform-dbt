"""Snowflake connection from environment variables (key-pair auth).

    python -m olist_ingest.snowflake_conn      # connection smoke test

All settings come from the environment (.env locally, GitHub Secrets in CI), so the
same code runs everywhere and no credential is ever written into the repo.
"""

import os
import sys

import snowflake.connector
from dotenv import load_dotenv

from olist_ingest.config import PROJECT_ROOT

REQUIRED = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH"]


def connect(role: str | None = None, warehouse: str | None = None):
    load_dotenv(PROJECT_ROOT / ".env")
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)} (see .env.example)")

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.path.expanduser(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]),
        private_key_password=os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or None,
        role=role or os.getenv("SNOWFLAKE_ROLE"),
        warehouse=warehouse or os.getenv("SNOWFLAKE_WAREHOUSE"),
        session_parameters={"QUERY_TAG": "olist_ingest"},
    )


def main() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select current_account_name(), current_user(), current_role(), "
            "current_warehouse(), current_version()"
        )
        account, user, role, wh, version = cur.fetchone()
        print(f"Connected: account={account} user={user} role={role} "
              f"warehouse={wh} snowflake={version}")

        # Prove the privileges match the design, not just that login works.
        cur.execute("select count(*) from olist_raw.information_schema.tables "
                    "where table_schema = 'OLIST'")
        print(f"OLIST_RAW.OLIST visible, tables so far: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
