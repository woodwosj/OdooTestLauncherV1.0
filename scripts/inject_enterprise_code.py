"""Inject Odoo enterprise licence metadata into the target database."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import psycopg

SQL_STATEMENTS = (
    "INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date) "
    "VALUES (%s, %s, 1, 1, %s, %s) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date"
)


def inject(
    host: str,
    port: int,
    user: str,
    password: str,
    dbname: str,
    code: str,
) -> None:
    timestamp = datetime.now(tz=timezone.utc)
    payloads = [
        ("database.enterprise_code", code, timestamp, timestamp),
        ("database.enterprise_privilege", "1", timestamp, timestamp),
    ]
    with psycopg.connect(  # type: ignore[arg-type]
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.executemany(SQL_STATEMENTS, payloads)
        conn.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject Odoo enterprise code.")
    parser.add_argument("--pg-host", default="127.0.0.1")
    parser.add_argument("--pg-port", type=int, required=True)
    parser.add_argument("--pg-user", required=True)
    parser.add_argument("--pg-password", default="odoo")
    parser.add_argument("--db-name", required=True)
    parser.add_argument("--code", required=True, help="Enterprise licence code string.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    inject(
        host=args.pg_host,
        port=args.pg_port,
        user=args.pg_user,
        password=args.pg_password,
        dbname=args.db_name,
        code=args.code,
    )


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
