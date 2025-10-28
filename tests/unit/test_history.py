from pathlib import Path

from cli.history import append_record, create_record, load_history, update_status


def test_history_roundtrip(tmp_path: Path) -> None:
    history_file = tmp_path / "history.log"
    record = create_record(
        run_id="odoo-test",
        edition="community",
        version="18.0",
        db_name="db",
        compose_file=tmp_path / "docker-compose.yml",
        run_root=tmp_path / "run",
        http_port=8069,
        longpoll_port=8072,
        pg_port=15432,
        seed="basic",
        keep_alive=False,
        status="starting",
    )
    append_record(history_file, record)
    saved = load_history(history_file)
    assert saved[0].run_id == "odoo-test"

    update_status(history_file, "odoo-test", "stopped")
    saved = load_history(history_file)
    assert saved[0].status == "stopped"
