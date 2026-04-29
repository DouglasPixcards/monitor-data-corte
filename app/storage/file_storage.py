from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from app.core.enums import EventoTipo
from app.core.models import Execucao, DadoCorte, Evento
from app.storage.repository import (
    ExecucaoRepository,
    DadosCorteRepository,
    EventoRepository,
)


class FileExecucaoRepository(ExecucaoRepository):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def _dir(self, processadora: str) -> Path:
        return self._base / "processadoras" / processadora / "execucoes"

    def salvar(self, execucao: Execucao) -> None:
        path = self._dir(execucao.processadora) / f"{execucao.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(execucao), ensure_ascii=False), encoding="utf-8")

    def listar(self, processadora: str) -> list[Execucao]:
        d = self._dir(processadora)
        if not d.exists():
            return []
        execucoes = [
            Execucao(**json.loads(arq.read_text(encoding="utf-8")))
            for arq in d.glob("*.json")
        ]
        execucoes.sort(key=lambda e: e.executada_em, reverse=True)
        return execucoes

    def buscar_ultima_ok(self, processadora: str) -> Execucao | None:
        for e in self.listar(processadora):
            if e.status == "ok":
                return e
        return None


class FileDadosCorteRepository(DadosCorteRepository):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path) / "dados_corte"

    def _path(self, execucao_id: str) -> Path:
        return self._base / f"{execucao_id}.json"

    def salvar_lote(self, dados: list[DadoCorte]) -> None:
        if not dados:
            return
        groups: dict[str, list[dict]] = defaultdict(list)
        for d in dados:
            groups[d.execucao_id].append(asdict(d))
        for execucao_id, records in groups.items():
            path = self._path(execucao_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    def buscar_por_execucao(self, execucao_id: str) -> list[DadoCorte]:
        path = self._path(execucao_id)
        if not path.exists():
            return []
        records = json.loads(path.read_text(encoding="utf-8"))
        return [DadoCorte(**r) for r in records]


class FileEventoRepository(EventoRepository):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def _path(self, processadora: str, date: str) -> Path:
        return self._base / "processadoras" / processadora / "eventos" / f"{date}.jsonl"

    def salvar_lote(self, eventos: list[Evento]) -> None:
        if not eventos:
            return
        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for e in eventos:
            date = e.detectado_em[:10]
            groups[(e.processadora, date)].append(asdict(e))
        for (processadora, date), records in groups.items():
            path = self._path(processadora, date)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
