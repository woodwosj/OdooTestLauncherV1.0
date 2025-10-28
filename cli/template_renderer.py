"""Jinja2 helpers for rendering compose files and other templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_template(source: Path, context: dict[str, Any], destination: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(source.parent)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(source.name)
    rendered = template.render(**context)
    destination.write_text(rendered, encoding="utf-8")
