"""Shared console utilities."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.theme import Theme

_console: Optional[Console] = None


def get_console() -> Console:
    """Provide a singleton Rich console."""
    global _console  # noqa: PLW0603
    if _console is None:
        _console = Console(
            theme=Theme(
                {
                    "info": "cyan",
                    "success": "green",
                    "warning": "yellow",
                    "error": "bold red",
                    "heading": "bold white",
                }
            )
        )
    return _console
