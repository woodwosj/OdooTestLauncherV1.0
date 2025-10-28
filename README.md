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

## Source Layout Requirements

The launcher reads Odoo sources directly from the filesystem; ensure your checkout matches the manifest defaults or update the manifest accordingly.

### Community edition

```
~/odoo-sandboxes/
└── community/
    └── 18.0/
        ├── odoo/            # core source tree
        ├── addons/          # community addons (manifest expects this path)
        └── ...               # rest of the upstream repo
```

Clone the official community repo (or copy a tarball) into `~/odoo-sandboxes/community/18.0`.

### Enterprise edition

```
~/odoo-sandboxes/
├── community/
│   └── 18.0/                # reused for base addons
└── enterprise/
    └── 18.0/
        ├── odoo/            # enterprise bundle (contains enterprise addons)
        ├── enterprise/      # optional extra packaging from installer
        └── addons/          # optional; not required by manifest
```

Place the licensed enterprise bundle under `~/odoo-sandboxes/enterprise/18.0` and ensure the `odoo/addons` directory (from the tarball/installer) is present. The manifest mounts community addons plus `enterprise/18.0/odoo/addons` so standard enterprise modules resolve correctly.

If you want to store sources elsewhere, edit `config/default_manifest.yml` (or your user manifest) to point `repo_path`, `addons`, and `extra_addons` to the actual locations.
