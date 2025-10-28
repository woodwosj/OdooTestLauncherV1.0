import subprocess
import sys


def test_cli_help() -> None:
    result = subprocess.run(  # noqa: S603,S607
        [sys.executable, "-m", "cli.main", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Manage disposable Odoo environments" in result.stdout
