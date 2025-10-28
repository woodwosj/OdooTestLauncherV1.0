# Odoo Test Build Launcher

The launcher provisions short-lived Odoo environments backed by Docker Compose, applies deterministic seeds, optionally runs test suites, and tears everything back down. This guide walks through the prerequisites, configuration, and day-to-day commands.

## Prerequisites

- Ubuntu 24.04 (or comparable) with Docker Engine and the new `docker compose` plugin available on the `$PATH`.
- Python 3.12+ for the CLI runtime.
- Cached Odoo sources located under `~/odoo-sandboxes/` as referenced in `config/default_manifest.yml` (see **Assumptions** below).
- Optional: export `ODOO_ENTERPRISE_CODE` before launching enterprise stacks.

Run `make install` to bootstrap a dedicated virtual environment with all CLI, lint, and test dependencies:

```bash
make install
source .venv/bin/activate
```

## Configuration

Use `odoo-launch init` to copy the default manifest to `~/.odoo-launch/config.yml`:

```bash
odoo-launch init --config ~/.odoo-launch/config.yml
```

The manifest controls edition metadata (repository paths, compose templates, ports, seed packs). You can edit the YAML to add additional versions or tweak defaults. The CLI auto-falls back to the in-repo `config/default_manifest.yml` when a user override is absent.

## Core Commands

| Command | Purpose |
| --- | --- |
| `odoo-launch validate` | Ensures Docker, compose, and manifest paths are healthy. Add `--require-enterprise` to enforce licence availability. |
| `odoo-launch init` | Writes a user-specific copy of the manifest. |
| `odoo-launch up` | Boots a disposable stack. Supports `--edition`, `--version`, `--seed`, `--module`, `--test-tags`, `--run-tests`, `--keep-alive`, and `--enterprise-code`. |
| `odoo-launch test` | Shortcut for `up --run-tests` with the same options. |
| `odoo-launch stop <run-id>` | Tears down a recorded run and prunes its temp directory. |
| `odoo-launch psql <run-id> --command "SELECT 1"` | Executes read-only SQL against the run's database. |
| `odoo-launch clean` | Removes stale run directories and invokes `docker system prune --volumes`. |

Each successful run writes metadata both to a JSON file under the run directory (`run.json`) and to `~/.odoo-launch/history.log` (JSONL). Use these logs to recover run IDs or compose file paths.

## Seeding and Enterprise Support

- Seed SQL lives under `seeds/<scenario>/`. The default `basic` seed creates a demo company and an admin contact.
- Python seed scripts can be registered in the manifest; they run through `odoo shell` inside the container.
- Enterprise licence injection happens immediately after seeding when a code is provided (via `--enterprise-code` or the `ODOO_ENTERPRISE_CODE` environment variable). The helper script updates `ir_config_parameter` for the active database.

## Testing and Tooling

- `make lint` runs Ruff and mypy on the codebase.
- `make test` executes unit, smoke, and e2e command tests (includes `scripts/run_smoke_tests.sh` which provisions community stacks).
- `make package` builds a distribution artifact using `python -m build`.

## Assumptions Logged

- The repository root doubles as the `~/odoo-launcher` project scaffold referenced in the planning document; manifests resolve relative paths accordingly.
- Community sources are cloned at `~/odoo-sandboxes/community/18.0`. Enterprise placeholders exist at `~/odoo-sandboxes/enterprise/18.0`; replace them with the actual enterprise checkout before running enterprise builds.
- The launcher binds containers to `127.0.0.1` ports. If collisions occur, it auto-increments until an open port is found.
- PostgreSQL connections and HTTP readiness checks target the host network; ensure Docker is configured with default bridge networking.
- Seed data expects a fresh database per run; the CLI creates the database when PostgreSQL is reachable.

Update the assumptions as you extend manifests or change directory layouts so future runs remain deterministic.
