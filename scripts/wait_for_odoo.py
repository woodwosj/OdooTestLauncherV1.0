"""Wait for an Odoo instance to become ready."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import psycopg
import psycopg.errors


@dataclass
class WaitConfig:
    pg_host: str
    pg_port: int
    pg_user: str
    pg_password: str
    db_name: str
    http_url: str
    pg_timeout: int
    pg_interval: float
    http_timeout: int
    http_interval: float


def wait_for_postgres(cfg: WaitConfig) -> None:
    """Block until PostgreSQL accepts connections or timeout occurs."""
    deadline = time.monotonic() + cfg.pg_timeout
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(  # type: ignore[arg-type]
                host=cfg.pg_host,
                port=cfg.pg_port,
                user=cfg.pg_user,
                password=cfg.pg_password,
                dbname="postgres",
                connect_timeout=int(cfg.pg_interval),
            ):
                return
        except psycopg.OperationalError as err:
            last_error = err
        time.sleep(cfg.pg_interval)
    raise TimeoutError(f"PostgreSQL readiness timed out: {last_error}")  # pragma: no cover


def wait_for_http(cfg: WaitConfig) -> None:
    """Block until HTTP endpoint returns a healthy status."""
    deadline = time.monotonic() + cfg.http_timeout
    last_error: Optional[Exception] = None
    with httpx.Client(timeout=cfg.http_interval, follow_redirects=True) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(cfg.http_url)
                if response.status_code < 500:
                    return
                last_error = RuntimeError(
                    f"status {response.status_code}: {response.text[:200]}"
                )
            except httpx.HTTPError as err:
                last_error = err
            time.sleep(cfg.http_interval)
    raise TimeoutError(f"Odoo HTTP readiness timed out: {last_error}")  # pragma: no cover


def wait(cfg: WaitConfig) -> None:
    wait_for_postgres(cfg)
    wait_for_http(cfg)


def _parse_args() -> WaitConfig:
    parser = argparse.ArgumentParser(description="Wait for Odoo readiness.")
    parser.add_argument("--pg-host", default="127.0.0.1")
    parser.add_argument("--pg-port", type=int, required=True)
    parser.add_argument("--pg-user", required=True)
    parser.add_argument("--pg-password", default="odoo")
    parser.add_argument("--db-name", required=True)
    parser.add_argument("--http-url", required=True)
    parser.add_argument("--pg-timeout", type=int, default=120)
    parser.add_argument("--pg-interval", type=float, default=3.0)
    parser.add_argument("--http-timeout", type=int, default=600)
    parser.add_argument("--http-interval", type=float, default=5.0)
    args = parser.parse_args()
    return WaitConfig(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        db_name=args.db_name,
        http_url=args.http_url,
        pg_timeout=args.pg_timeout,
        pg_interval=args.pg_interval,
        http_timeout=args.http_timeout,
        http_interval=args.http_interval,
    )


def main() -> None:
    cfg = _parse_args()
    wait(cfg)


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
