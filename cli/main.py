"""Entry point for the Odoo Test Build Launcher CLI."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import psycopg
import typer

from scripts.inject_enterprise_code import inject as inject_enterprise_code
from scripts.wait_for_odoo import WaitConfig, wait_for_http, wait_for_postgres

from .docker_ops import DockerRunner
from .exceptions import (
    DockerError,
    EnterpriseError,
    LauncherError,
    ManifestError,
    SeedError,
    ValidationError,
)
from .history import append_record, create_record, find_record, load_history, update_status
from .logger import get_console
from .manifest import EditionVersionConfig, Manifest, load_manifest
from .template_renderer import render_template
from .utils import (
    ensure_available_port,
    ensure_directory,
    expand_path,
    generate_run_id,
    random_db_name,
)

console = get_console()
app = typer.Typer(help="Manage disposable Odoo environments for testing.")

DEFAULT_CONFIG_PATH = Path("~/.odoo-launch/config.yml")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = REPO_ROOT / "config" / "default_manifest.yml"


def _resolve_config_path(path: Optional[Path]) -> Path:
    if path is None:
        candidate = expand_path(str(DEFAULT_CONFIG_PATH))
        if candidate.exists():
            return candidate
        return DEFAULT_MANIFEST_PATH
    resolved = expand_path(str(path))
    return resolved if resolved.exists() else DEFAULT_MANIFEST_PATH


def _load_manifest(config: Optional[Path]) -> Manifest:
    path = _resolve_config_path(config)
    return load_manifest(path)


def _prepare_source_mounts(
    entry: EditionVersionConfig,
) -> tuple[list[dict[str, object]], list[str]]:
    mounts: list[dict[str, object]] = []
    addon_targets: list[str] = []
    for idx, addon_path in enumerate(entry.addons):
        target = f"/mnt/extra-addons/addons_{idx:02d}"
        mounts.append(
            {
                "host": str(addon_path),
                "target": target,
                "read_only": True,
            }
        )
        addon_targets.append(target)
    for idx, addon_path in enumerate(entry.extra_addons):
        target = f"/mnt/extra-addons/custom_{idx:02d}"
        mounts.append(
            {
                "host": str(addon_path),
                "target": target,
                "read_only": False,
            }
        )
        addon_targets.append(target)
    return mounts, addon_targets


def _render_compose(
    manifest: Manifest,
    entry: EditionVersionConfig,
    run_root: Path,
    run_id: str,
    db_name: str,
    db_user: str,
    db_password: str,
    http_port: int,
    longpoll_port: int,
    pg_port: int,
    enterprise_code: Optional[str],
) -> Path:
    compose_file = run_root / "docker-compose.yml"
    source_mounts, addon_targets = _prepare_source_mounts(entry)
    addons_path = ",".join(["/usr/lib/python3/dist-packages/odoo/addons", *addon_targets])
    context = {
        "postgres_image": manifest.defaults.postgres_image,
        "odoo_image": entry.image,
        "run_id": run_id,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "http_port": http_port,
        "longpoll_port": longpoll_port,
        "pg_port": pg_port,
        "run_root": str(run_root),
        "source_mounts": source_mounts,
        "enterprise_code": enterprise_code,
        "addons_path": addons_path,
    }
    render_template(entry.compose_template, context, compose_file)
    return compose_file


def _apply_sql_seed(
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
    sql_path: Path,
) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    with psycopg.connect(  # type: ignore[arg-type]
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=db_name,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()


def _force_remove(path: Path) -> None:
    """Best-effort removal of run artifacts with relaxed permissions."""
    if not path.exists():
        return
    for sub_path in sorted(path.rglob("*"), reverse=True):
        try:
            sub_path.chmod(0o777)
        except PermissionError:
            pass
    try:
        path.chmod(0o777)
    except PermissionError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def _run_seed_suite(
    entry: EditionVersionConfig,
    seed_name: str,
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
    docker: DockerRunner,
    compose_file: Path,
) -> None:
    try:
        seed_cfg = entry.seeds[seed_name]
    except KeyError as exc:
        raise SeedError(f"Unknown seed '{seed_name}' for {entry.edition} {entry.version}") from exc

    for sql_file in seed_cfg.sql_files:
        _apply_sql_seed(host, port, user, password, db_name, sql_file)
    for script in seed_cfg.scripts:
        payload = script.read_text(encoding="utf-8")
        docker.exec(
            compose_file,
            "odoo",
            ["odoo", "shell", "-d", db_name, "--no-http"],
            input_data=payload,
        )


def _run_tests(
    docker: DockerRunner,
    compose_file: Path,
    db_name: str,
    modules: List[str],
    test_tags: Optional[str],
) -> None:
    command = ["odoo", "-d", db_name, "--test-enable", "--stop-after-init", "--http-port=0"]
    if modules:
        command.extend(["-u", ",".join(modules)])
    if test_tags:
        command.extend(["--test-tags", test_tags])
    result = docker.exec(compose_file, "odoo", command, check=False)
    if result.returncode != 0:
        raise LauncherError(f"Odoo tests failed:\n{result.stdout}\n{result.stderr}")


def _enterprise_code_from_env(explicit: Optional[str]) -> Optional[str]:
    return explicit or os.getenv("ODOO_ENTERPRISE_CODE")


def _handle_enterprise(
    entry: EditionVersionConfig,
    enterprise_code: Optional[str],
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
) -> None:
    if entry.requires_enterprise_code:
        if not enterprise_code:
            raise EnterpriseError(
                "Enterprise edition selected but no licence code provided. "
                "Set ODOO_ENTERPRISE_CODE or pass --enterprise-code."
            )
        inject_enterprise_code(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name,
            code=enterprise_code,
        )


def _print_run_summary(record_path: Path, http_port: int, db_name: str) -> None:
    console.print("[success]Odoo environment is ready[/success]")
    console.print(f"[info]Run manifest:[/info] {record_path}")
    console.print(f"[info]Open http://localhost:{http_port}?db={db_name}[/info]")


@app.command()
def init(
    config_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH,
        "--config",
        help="Path where the manifest copy should be written.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config if present."),
) -> None:
    """Bootstrap launcher configuration under ~/.odoo-launch/."""
    destination = expand_path(str(config_path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        console.print(f"[warning]Config already exists at {destination}, use --force to overwrite.[/warning]")
        raise typer.Exit(code=1)
    destination.write_text(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[success]Manifest written to {destination}[/success]")


def _execute_up(
    edition: str,
    version: str,
    seed: Optional[str],
    run_tests_flag: bool,
    modules: List[str],
    test_tags: Optional[str],
    keep_alive: bool,
    enterprise_code: Optional[str],
    config_path: Optional[Path],
) -> None:
    manifest = _load_manifest(config_path)
    entry = manifest.get_version(edition, version)

    run_id = generate_run_id()
    db_name = random_db_name(prefix=f"{edition}_{version.replace('.', '_')}")

    http_port = ensure_available_port(entry.http_port)
    longpoll_port = ensure_available_port(entry.longpoll_port)
    pg_port = ensure_available_port(entry.pg_port)

    run_root = ensure_directory(manifest.defaults.temp_run_root / run_id)
    enterprise_payload = _enterprise_code_from_env(enterprise_code)
    compose_file = _render_compose(
        manifest,
        entry,
        run_root,
        run_id,
        db_name,
        db_user="odoo",
        db_password="odoo",
        http_port=http_port,
        longpoll_port=longpoll_port,
        pg_port=pg_port,
        enterprise_code=enterprise_payload,
    )

    docker = DockerRunner(manifest.defaults.compose_bin)

    record = create_record(
        run_id=run_id,
        edition=edition,
        version=version,
        db_name=db_name,
        compose_file=compose_file,
        run_root=run_root,
        http_port=http_port,
        longpoll_port=longpoll_port,
        pg_port=pg_port,
        seed=seed or entry.default_seed,
        keep_alive=keep_alive,
        status="starting",
    )
    append_record(manifest.defaults.history_log, record)
    record_logged = True

    try:
        console.print(f"[info]Starting run {run_id} ({edition} {version})[/info]")
        docker.up(compose_file)

        wait_cfg = WaitConfig(
            pg_host="127.0.0.1",
            pg_port=pg_port,
            pg_user="odoo",
            pg_password="odoo",
            db_name=db_name,
            http_url=f"http://127.0.0.1:{http_port}/web/login",
            pg_timeout=manifest.defaults.readiness.pg_timeout,
            pg_interval=manifest.defaults.readiness.pg_interval,
            http_timeout=manifest.defaults.readiness.http_timeout,
            http_interval=manifest.defaults.readiness.http_interval,
        )

        wait_for_postgres(wait_cfg)
        wait_for_http(wait_cfg)
        seed_to_use = seed or entry.default_seed
        _run_seed_suite(
            entry,
            seed_to_use,
            host="127.0.0.1",
            port=pg_port,
            user="odoo",
            password="odoo",
            db_name=db_name,
            docker=docker,
            compose_file=compose_file,
        )

        _handle_enterprise(
            entry,
            enterprise_payload,
            host="127.0.0.1",
            port=pg_port,
            user="odoo",
            password="odoo",
            db_name=db_name,
        )

        if run_tests_flag:
            console.print("[info]Running Odoo test suite[/info]")
            _run_tests(docker, compose_file, db_name, modules, test_tags)

        new_status = "running" if keep_alive else "stopped"
        record.seed = seed_to_use
        record.status = new_status

        run_metadata_path = run_root / "run.json"
        run_metadata_path.write_text(json.dumps(record.__dict__, indent=2, default=str), encoding="utf-8")

        _print_run_summary(run_metadata_path, http_port, db_name)

        if not keep_alive:
            console.print("[info]Tearing down because --keep-alive not set[/info]")
            docker.down(compose_file)
            _force_remove(run_root)
        else:
            console.print(f"[info]Run {run_id} will remain active until stopped[/info]")

        update_status(manifest.defaults.history_log, run_id, new_status)
    except Exception as exc:  # pragma: no cover - top-level guard
        docker.down(compose_file)
        if record_logged:
            update_status(manifest.defaults.history_log, run_id, "failed")
        _force_remove(run_root)
        raise exc


@app.command()
def up(
    edition: str = typer.Option("community", help="Edition to launch (community or enterprise)."),
    version: str = typer.Option("18.0", help="Odoo version to launch."),
    seed: Optional[str] = typer.Option(None, help="Seed scenario to apply."),
    run_tests: bool = typer.Option(False, "--run-tests/--skip-tests", help="Execute Odoo tests."),
    modules: List[str] = typer.Option(
        [],
        "--module",
        "-m",
        help="Module names to update/test (repeatable).",
    ),
    test_tags: Optional[str] = typer.Option(None, help="Odoo --test-tags expression."),
    keep_alive: bool = typer.Option(False, help="Keep the stack running after setup completes."),
    enterprise_code: Optional[str] = typer.Option(
        None, help="Enterprise licence code (or set ODOO_ENTERPRISE_CODE)."
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Alternate manifest path.",
    ),
) -> None:
    """Render and launch a disposable Odoo stack."""
    try:
        _execute_up(
            edition=edition,
            version=version,
            seed=seed,
            run_tests_flag=run_tests,
            modules=modules,
            test_tags=test_tags,
            keep_alive=keep_alive,
            enterprise_code=enterprise_code,
            config_path=config,
        )
    except LauncherError as err:
        console.print(f"[error]{err}[/error]")
        raise typer.Exit(code=1) from err


@app.command()
def test(
    edition: str = typer.Option("community", help="Edition to launch."),
    version: str = typer.Option("18.0", help="Version to test."),
    seed: Optional[str] = typer.Option(None, help="Seed scenario to apply."),
    modules: List[str] = typer.Option([], "--module", "-m", help="Modules to update/test."),
    test_tags: Optional[str] = typer.Option(None, help="Odoo test tags expression."),
    keep_alive: bool = typer.Option(False, help="Keep stack running after tests."),
    enterprise_code: Optional[str] = typer.Option(None, help="Enterprise licence code."),
    config: Optional[Path] = typer.Option(None, "--config", help="Alternate manifest path."),
) -> None:
    """Shortcut for running Odoo tests with automatic teardown."""
    up(
        edition=edition,
        version=version,
        seed=seed,
        run_tests=True,
        modules=modules,
        test_tags=test_tags,
        keep_alive=keep_alive,
        enterprise_code=enterprise_code,
        config=config,
    )


@app.command()
def stop(
    run_id: str = typer.Argument(..., help="Run identifier to stop."),
    config: Optional[Path] = typer.Option(None, "--config", help="Alternate manifest path."),
) -> None:
    """Stop a running environment."""
    manifest = _load_manifest(config)
    record = find_record(manifest.defaults.history_log, run_id)
    docker = DockerRunner(manifest.defaults.compose_bin)
    docker.down(record.compose_file)
    _force_remove(record.run_root)
    update_status(manifest.defaults.history_log, run_id, "stopped")
    console.print(f"[success]Stopped run {run_id}[/success]")


@app.command()
def clean(
    config: Optional[Path] = typer.Option(None, "--config", help="Alternate manifest path."),
) -> None:
    """Remove stale run directories and prune Docker artefacts."""
    manifest = _load_manifest(config)
    records = load_history(manifest.defaults.history_log)
    active_ids = {rec.run_id for rec in records if rec.status == "running"}
    for path in manifest.defaults.temp_run_root.glob("odoo-*"):
        if path.is_dir() and path.name not in active_ids:
            shutil.rmtree(path, ignore_errors=True)
            console.print(f"[info]Removed stale run directory {path}[/info]")
    console.print("[info]Pruning dangling Docker resources[/info]")
    try:
        subprocess.run(  # noqa: S603,S607 - intentional Docker invocation
            ["docker", "system", "prune", "--force", "--volumes"],
            check=False,
        )
    except Exception:  # pragma: no cover - defensive
        console.print("[warning]docker system prune failed (ignored)[/warning]")


def _check_command(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(  # noqa: S603,S607
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, result.stdout.strip() or "OK"
    except FileNotFoundError:
        return False, "command not found"
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        return False, message


def _validate_docker_tooling(manifest: Manifest, errors: list[str]) -> None:
    ok, msg = _check_command(["docker", "info", "--format", "{{json .ServerVersion}}"])
    if not ok:
        errors.append(f"Docker check failed: {msg}")
    else:
        console.print(f"[info]Docker detected (server {msg})[/info]")

    compose_cmd = shlex.split(manifest.defaults.compose_bin) + ["version"]
    ok, msg = _check_command(compose_cmd)
    if not ok:
        errors.append(f"docker compose check failed: {msg}")
    else:
        console.print(f"[info]docker compose detected ({msg})[/info]")


def _validate_repo_paths(manifest: Manifest, errors: list[str]) -> None:
    for edition, payload in manifest.editions.items():
        for version, entry in payload.items():
            if not entry.repo_path.exists():
                errors.append(f"Repo path missing for {edition} {version}: {entry.repo_path}")
            for addon_path in [*entry.addons, *entry.extra_addons]:
                if not addon_path.exists():
                    errors.append(f"Addon path missing: {addon_path}")


@app.command()
def validate(
    config: Optional[Path] = typer.Option(None, "--config", help="Alternate manifest path."),
    require_enterprise: bool = typer.Option(
        False, "--require-enterprise", help="Fail if no enterprise licence code is configured."
    ),
) -> None:
    """Validate Docker tooling, manifest paths, and optional enterprise requirements."""
    manifest = _load_manifest(config)
    errors: list[str] = []

    _validate_docker_tooling(manifest, errors)
    _validate_repo_paths(manifest, errors)

    if require_enterprise and not _enterprise_code_from_env(None):
        errors.append(
            "Enterprise licence not configured. Set ODOO_ENTERPRISE_CODE or provide --enterprise-code."
        )

    if errors:
        for err in errors:
            console.print(f"[error]{err}[/error]")
        raise typer.Exit(code=1)

    console.print("[success]Environment validation passed[/success]")


@app.command()
def psql(
    run_id: str = typer.Argument(..., help="Run identifier to target."),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="SQL command to execute."),
    config: Optional[Path] = typer.Option(None, "--config", help="Alternate manifest path."),
) -> None:
    """Execute read-only SQL commands against a running environment."""
    manifest = _load_manifest(config)
    record = find_record(manifest.defaults.history_log, run_id)
    if command is None:
        console.print(
            "[warning]Interactive psql is not supported in this environment. "
            "Provide --command SQL to execute a statement."
        )
        raise typer.Exit(code=1)
    docker = DockerRunner(manifest.defaults.compose_bin)
    result = docker.exec(
        record.compose_file,
        "db",
        ["psql", "-U", "odoo", "-d", record.db_name, "-c", command],
        check=False,
    )
    console.print(result.stdout)
    if result.returncode != 0:
        console.print(f"[error]{result.stderr}[/error]")
        raise typer.Exit(code=result.returncode)


def main() -> None:
    try:
        app()
    except (LauncherError, ManifestError, ValidationError, DockerError) as err:
        console.print(f"[error]{err}[/error]")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
