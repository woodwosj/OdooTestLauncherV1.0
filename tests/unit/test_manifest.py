from cli.main import DEFAULT_MANIFEST_PATH
from cli.manifest import load_manifest


def test_default_manifest_loads() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    community = manifest.get_version("community", "18.0")
    assert community.repo_path.exists()
    assert community.compose_template.exists()
    assert community.http_port > 0
