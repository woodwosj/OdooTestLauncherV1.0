"""Utility helpers for the launcher."""

from __future__ import annotations

import secrets
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

from .exceptions import ValidationError


def expand_path(path_str: str) -> Path:
    """Expand user and resolve a filesystem path."""
    return Path(path_str).expanduser().resolve()


def ensure_directory(path: Path, *, mode: int | None = None) -> Path:
    """Create directory if needed and optionally set permissions."""
    path.mkdir(parents=True, exist_ok=True)
    if mode is not None:
        path.chmod(mode)
    return path


def generate_run_id(prefix: str = "odoo") -> str:
    """Produce a run identifier with timestamp component."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}-{timestamp}-{suffix}"


def random_db_name(prefix: str = "odoo") -> str:
    """Generate a predictable-yet-unique database name."""
    return f"{prefix}_{secrets.token_hex(4)}"


def assert_ports_available(ports: Iterable[int]) -> None:
    """Raise if any requested port is already bound."""
    collisions: list[Tuple[str, int]] = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", port))
        if result == 0:
            collisions.append(("127.0.0.1", port))
    if collisions:
        formatted = ", ".join(f"{host}:{port}" for host, port in collisions)
        raise ValidationError(f"Ports already in use: {formatted}")


def ensure_available_port(preferred: int, *, attempts: int = 20) -> int:
    """Find an open port, starting at the preferred value."""
    port = preferred
    for _ in range(attempts):
        if not _port_in_use(port):
            return port
        port += 1
    raise ValidationError(f"Unable to find free port near {preferred}")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0
