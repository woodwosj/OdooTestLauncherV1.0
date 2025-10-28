# Odoo Test Build Launcher

Typer-powered CLI for orchestrating disposable Odoo stacks. The tool renders Docker Compose environments from manifest metadata, seeds deterministic fixtures, optionally executes Odoo's test harness, and records every run for later teardown.

## Feature Highlights

- **Manifest-driven orchestration** – versions, editions, ports, and seed packs live in YAML.
- **Deterministic seeding** – SQL and Python scripts populate fresh databases per run.
- **Enterprise-aware flows** – licence injector updates `ir_config_parameter` when a code is supplied.
- **Safety rails** – readiness probes, port collision avoidance, JSONL run history, and automatic cleanup.

## Quick Start

```bash
make install
source .venv/bin/activate
odoo-launch validate
odoo-launch up --edition community --version 18.0 --keep-alive
```

Stop the run later via:

```bash
odoo-launch stop <run-id>
```

See `docs/usage.md` for full documentation, including configuration, command reference, and recorded assumptions.
