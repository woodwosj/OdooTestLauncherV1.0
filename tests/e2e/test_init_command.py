import subprocess
import sys
from pathlib import Path


def test_init_writes_manifest(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    result = subprocess.run(  # noqa: S603,S607
        [
            sys.executable,
            "-m",
            "cli.main",
            "init",
            "--config",
            str(config_path),
            "--force",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert config_path.exists()
    assert "Manifest written" in result.stdout
