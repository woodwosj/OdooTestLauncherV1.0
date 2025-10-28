"""Manifest parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from .exceptions import ManifestError
from .utils import ensure_directory, expand_path


@dataclass(frozen=True)
class ReadinessConfig:
    http_timeout: int
    http_interval: int
    pg_timeout: int
    pg_interval: int


@dataclass(frozen=True)
class Defaults:
    temp_run_root: Path
    history_log: Path
    docker_bin: str
    compose_bin: str
    postgres_image: str
    timezone: str
    readiness: ReadinessConfig


@dataclass(frozen=True)
class SeedConfig:
    name: str
    sql_files: List[Path]
    scripts: List[Path]


@dataclass(frozen=True)
class EditionVersionConfig:
    edition: str
    version: str
    repo_path: Path
    compose_template: Path
    image: str
    addons: List[Path]
    extra_addons: List[Path]
    http_port: int
    longpoll_port: int
    pg_port: int
    default_seed: str
    requires_enterprise_code: bool
    seeds: Dict[str, SeedConfig]


@dataclass(frozen=True)
class Manifest:
    defaults: Defaults
    editions: Dict[str, Dict[str, EditionVersionConfig]]

    def get_version(self, edition: str, version: str) -> EditionVersionConfig:
        """Fetch manifest entry for edition/version pair."""
        try:
            return self.editions[edition][version]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ManifestError(f"Unknown edition/version: {edition} {version}") from exc


def load_manifest(path: Path) -> Manifest:
    """Load manifest YAML and normalise paths."""
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    try:
        defaults = _parse_defaults(raw.get("defaults", {}))
        editions = _parse_editions(raw.get("editions", {}), defaults, base_dir=path.parent)
    except KeyError as exc:  # pragma: no cover - defensive
        raise ManifestError(f"Manifest missing required section: {exc}") from exc

    ensure_directory(defaults.temp_run_root)
    ensure_directory(defaults.history_log.parent)

    return Manifest(defaults=defaults, editions=editions)


def _parse_defaults(data: dict) -> Defaults:
    try:
        readiness_data = data["readiness"]
    except KeyError as exc:
        raise ManifestError("defaults.readiness section missing") from exc

    readiness = ReadinessConfig(
        http_timeout=int(readiness_data.get("http_timeout", 600)),
        http_interval=int(readiness_data.get("http_interval", 5)),
        pg_timeout=int(readiness_data.get("pg_timeout", 120)),
        pg_interval=int(readiness_data.get("pg_interval", 3)),
    )

    return Defaults(
        temp_run_root=expand_path(data.get("temp_run_root", "~/.odoo-launch/runs")),
        history_log=expand_path(data.get("history_log", "~/.odoo-launch/history.log")),
        docker_bin=data.get("docker_bin", "docker"),
        compose_bin=data.get("compose_bin", "docker compose"),
        postgres_image=data.get("postgres_image", "postgres:16"),
        timezone=data.get("timezone", "UTC"),
        readiness=readiness,
    )


def _parse_editions(
    data: dict, defaults: Defaults, base_dir: Path
) -> Dict[str, Dict[str, EditionVersionConfig]]:
    del defaults  # not currently used, reserved for future defaults handling.
    editions: Dict[str, Dict[str, EditionVersionConfig]] = {}
    for edition_name, versions in data.items():
        editions[edition_name] = {}
        for version, payload in versions.items():
            repo_path = _resolve_relative(payload["repo_path"], base_dir)
            if not repo_path.exists():
                raise ManifestError(f"Configured repo path missing: {repo_path}")

            compose_template = _resolve_relative(payload["compose_template"], base_dir)
            if not compose_template.exists():
                raise ManifestError(f"Compose template missing: {compose_template}")

            addons = [
                _normalise_path(path_candidate, repo_path)
                for path_candidate in payload.get("addons", [])
            ]
            extra_addons = [
                _normalise_path(path_candidate, repo_path)
                for path_candidate in payload.get("extra_addons", [])
            ]

            for path in [*addons, *extra_addons]:
                if not path.exists():
                    raise ManifestError(f"Addon path missing: {path}")

            seeds = _parse_seeds(payload.get("seeds", {}), repo_path)
            requires_enterprise = payload.get("requires_enterprise_code", False)

            editions[edition_name][version] = EditionVersionConfig(
                edition=edition_name,
                version=version,
                repo_path=repo_path,
                compose_template=compose_template,
                image=payload.get("image", "odoo:18.0"),
                addons=addons,
                extra_addons=extra_addons,
                http_port=int(payload["http_port"]),
                longpoll_port=int(payload["longpoll_port"]),
                pg_port=int(payload.get("pg_port", 15432)),
                default_seed=payload.get("default_seed", "basic"),
                requires_enterprise_code=requires_enterprise,
                seeds=seeds,
            )
    return editions


def _parse_seeds(seeds: dict, repo_path: Path) -> Dict[str, SeedConfig]:
    parsed: Dict[str, SeedConfig] = {}
    for name, payload in seeds.items():
        sql_files = [
            _normalise_path(candidate, repo_path) for candidate in payload.get("sql", [])
        ]
        scripts = [
            _normalise_path(candidate, repo_path) for candidate in payload.get("scripts", [])
        ]
        parsed[name] = SeedConfig(name=name, sql_files=sql_files, scripts=scripts)
    return parsed


def _normalise_path(candidate: str, repo_path: Path) -> Path:
    if "{{ repo_path }}" in candidate:
        candidate = candidate.replace("{{ repo_path }}", str(repo_path))
    return expand_path(candidate)


def _resolve_relative(candidate: str, base_dir: Path) -> Path:
    path_candidate = Path(candidate)
    if not path_candidate.is_absolute() and not str(path_candidate).startswith("~"):
        return (base_dir / path_candidate).resolve()
    return expand_path(str(path_candidate))
