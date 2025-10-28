#!/usr/bin/env bash

# Basic smoke tests for the Odoo Test Build Launcher CLI.
# Ensures both "up" and "test" flows succeed for community edition.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_BIN="${PROJECT_ROOT}/.venv/bin/odoo-launch"

if [[ ! -x "${CLI_BIN}" ]]; then
  echo "ERROR: ${CLI_BIN} not found or not executable. Run 'make install' first." >&2
  exit 1
fi

echo "[smoke] Validating environment..."
"${CLI_BIN}" validate

echo "[smoke] Running community up flow..."
"${CLI_BIN}" up --edition community --version 18.0 --seed basic

echo "[smoke] Running community test flow..."
"${CLI_BIN}" test --edition community --version 18.0 --seed basic --module base --test-tags dummy

echo "[smoke] Smoke tests completed successfully."
