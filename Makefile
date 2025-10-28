PYTHON ?= python3
VENV ?= .venv

.PHONY: install lint test test-cli package format

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e .[dev]

lint:
	$(VENV)/bin/ruff check cli scripts tests
	$(VENV)/bin/mypy cli

test:
	$(VENV)/bin/pytest
	./scripts/run_smoke_tests.sh

test-cli:
	$(VENV)/bin/pytest tests/unit tests/smoke

package:
	$(VENV)/bin/pip install build
	$(VENV)/bin/python -m build
