"""History log management for launcher runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .exceptions import ManifestError


@dataclass
class HistoryRecord:
    run_id: str
    edition: str
    version: str
    db_name: str
    compose_file: Path
    run_root: Path
    http_port: int
    longpoll_port: int
    pg_port: int
    seed: str
    started_at: str
    status: str = "running"
    keep_alive: bool = False

    def to_json(self) -> str:
        payload = asdict(self)
        payload["compose_file"] = str(self.compose_file)
        payload["run_root"] = str(self.run_root)
        return json.dumps(payload)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryRecord":
        return cls(
            run_id=data["run_id"],
            edition=data["edition"],
            version=data["version"],
            db_name=data["db_name"],
            compose_file=Path(data["compose_file"]),
            run_root=Path(data["run_root"]),
            http_port=int(data["http_port"]),
            longpoll_port=int(data["longpoll_port"]),
            pg_port=int(data["pg_port"]),
            seed=data["seed"],
            started_at=data["started_at"],
            status=data.get("status", "running"),
            keep_alive=bool(data.get("keep_alive", False)),
        )


def append_record(history_path: Path, record: HistoryRecord) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(record.to_json())
        handle.write("\n")


def load_history(history_path: Path) -> List[HistoryRecord]:
    if not history_path.exists():
        return []
    records: List[HistoryRecord] = []
    with history_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(HistoryRecord.from_dict(json.loads(line)))
            except json.JSONDecodeError:  # pragma: no cover - defensive
                continue
    return records


def find_record(history_path: Path, run_id: str) -> HistoryRecord:
    for record in load_history(history_path):
        if record.run_id == run_id:
            return record
    raise ManifestError(f"Run id not found in history: {run_id}")


def update_status(history_path: Path, run_id: str, status: str) -> None:
    records = load_history(history_path)
    updated = False
    with history_path.open("w", encoding="utf-8") as handle:
        for record in records:
            if record.run_id == run_id:
                record.status = status
                updated = True
            handle.write(record.to_json())
            handle.write("\n")
    if not updated:
        raise ManifestError(f"Run id not found in history: {run_id}")


def create_record(
    run_id: str,
    edition: str,
    version: str,
    db_name: str,
    compose_file: Path,
    run_root: Path,
    http_port: int,
    longpoll_port: int,
    pg_port: int,
    seed: str,
    keep_alive: bool,
    status: str = "running",
) -> HistoryRecord:
    return HistoryRecord(
        run_id=run_id,
        edition=edition,
        version=version,
        db_name=db_name,
        compose_file=compose_file,
        run_root=run_root,
        http_port=http_port,
        longpoll_port=longpoll_port,
        pg_port=pg_port,
        seed=seed,
        started_at=datetime.now(tz=timezone.utc).isoformat(),
        status=status,
        keep_alive=keep_alive,
    )
