from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.repository import StorageRepository


class FileStorageRepository(StorageRepository):
    def __init__(self, base_path: str):
        self._base_path = Path(base_path)

    def _processadora_dir(self, processadora: str) -> Path:
        return self._base_path / "processadoras" / processadora.lower().strip()

    def _latest_path(self, processadora: str) -> Path:
        return self._processadora_dir(processadora) / "latest.json"

    def _snapshots_dir(self, processadora: str) -> Path:
        return self._processadora_dir(processadora) / "snapshots"

    def _executions_dir(self, processadora: str) -> Path:
        return self._processadora_dir(processadora) / "executions"

    def _events_dir(self, processadora: str) -> Path:
        return self._processadora_dir(processadora) / "events"

    def _ensure_dirs(self, processadora: str) -> None:
        self._processadora_dir(processadora).mkdir(parents=True, exist_ok=True)
        self._snapshots_dir(processadora).mkdir(parents=True, exist_ok=True)
        self._executions_dir(processadora).mkdir(parents=True, exist_ok=True)
        self._events_dir(processadora).mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = path.with_suffix(path.suffix + ".tmp")

        with open(temp_path, "w", encoding="utf-8") as arquivo:
            json.dump(data, arquivo, ensure_ascii=False, indent=4)

        temp_path.replace(path)

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read().strip()

        if not conteudo:
            return None

        return json.loads(conteudo)

    def load_latest_snapshot(self, processadora: str) -> dict | None:
        return self._read_json(self._latest_path(processadora))

    def save_execution(self, processadora: str, execution: dict) -> None:
        self._ensure_dirs(processadora)

        execution_id = execution.get("execution_id")
        if not execution_id:
            raise ValueError("execution_id é obrigatório para salvar execution.")

        path = self._executions_dir(processadora) / f"{execution_id}.json"
        self._write_json(path, execution)

    def save_snapshot(self, processadora: str, snapshot: dict) -> None:
        self._ensure_dirs(processadora)

        snapshot_id = snapshot.get("snapshot_id")
        if not snapshot_id:
            raise ValueError("snapshot_id é obrigatório para salvar snapshot.")

        path = self._snapshots_dir(processadora) / f"{snapshot_id}.json"
        self._write_json(path, snapshot)

    def save_latest_snapshot(self, processadora: str, snapshot: dict) -> None:
        self._ensure_dirs(processadora)
        self._write_json(self._latest_path(processadora), snapshot)

    def append_events(self, processadora: str, events: list[dict]) -> None:
        if not events:
            return

        self._ensure_dirs(processadora)

        for event in events:
            detected_at = event.get("detected_at")
            if not detected_at:
                raise ValueError("detected_at é obrigatório para salvar evento.")

            data_arquivo = detected_at[:10]
            path = self._events_dir(processadora) / f"{data_arquivo}.jsonl"

            with open(path, "a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(event, ensure_ascii=False))
                arquivo.write("\n")