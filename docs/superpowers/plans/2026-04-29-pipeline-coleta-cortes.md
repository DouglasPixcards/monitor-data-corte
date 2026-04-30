# Pipeline de Coleta de Datas de Corte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesenhar o pipeline de comparação e alerta do monitor-data-corte com modelos de domínio tipados, repositórios DB-ready, orquestrador de serviços e notificação via e-mail SMTP.

**Architecture:** Um `ColetaOrchestrator` coordena cinco serviços em sequência: coleta (scrapers existentes) → carrega dados anteriores → salva execução + dados atuais → compara via `ComparadorService` → persiste eventos → envia digest de e-mail se houver mudanças de `data_corte`. Todos os dados são mantidos para auditoria; nada é deletado.

**Tech Stack:** Python 3.11+, FastAPI, Playwright, `dataclasses`, `smtplib` (stdlib), `pytest`, `pytest-mock`.

---

## Arquivos criados/modificados

| Ação | Arquivo | Responsabilidade |
|---|---|---|
| **Criar** | `app/core/models.py` | Dataclasses `Execucao`, `DadoCorte`, `Evento` |
| **Modificar** | `app/core/enums.py` | Adicionar `EventoTipo` com 4 valores |
| **Modificar** | `app/core/settings.py` | Adicionar variáveis SMTP |
| **Reescrever** | `app/storage/repository.py` | 3 interfaces ABC sem conceito de arquivo |
| **Reescrever** | `app/storage/file_storage.py` | Implementações das 3 interfaces em arquivo |
| **Reescrever** | `app/services/comparador_service.py` | `ComparadorService` — recebe listas, retorna `list[Evento]` |
| **Criar** | `app/services/notificacao/base.py` | `NotificadorBase` ABC |
| **Criar** | `app/services/notificacao/smtp.py` | `EmailSMTPNotificador` |
| **Criar** | `app/services/notificacao/digest_builder.py` | `DigestBuilder` — monta assunto + HTML |
| **Criar** | `app/services/notificacao/__init__.py` | (vazio) |
| **Criar** | `app/services/orchestrator.py` | `ColetaOrchestrator` — pipeline completo |
| **Reescrever** | `app/api/main.py` | Endpoints usando orquestrador |
| **Deletar** | `app/services/collector_service.py` | Substituído por `orchestrator.py` |
| **Deletar** | `app/services/comparator.py` | Substituído por `comparador_service.py` |
| **Deletar** | `app/services/events.py` | Lógica absorvida pelo `comparador_service.py` |
| **Deletar** | `app/services/alert.py` | Substituído por `notificacao/` |
| **Criar** | `tests/__init__.py` | (vazio) |
| **Criar** | `tests/core/test_models.py` | Testes dos dataclasses |
| **Criar** | `tests/storage/test_file_storage.py` | Testes de round-trip do storage |
| **Criar** | `tests/services/test_comparador_service.py` | Testes de lógica de comparação |
| **Criar** | `tests/services/notificacao/test_digest_builder.py` | Testes do builder de e-mail |
| **Criar** | `tests/services/test_orchestrator.py` | Testes do pipeline com mocks |

**Arquivos que NÃO mudam:** `app/scrapers/*`, `app/services/coleta_service.py`, `app/auth/*`, `app/core/processadoras.json`, `app/core/loader.py`, `app/utils/*`, `app/services/storage_helpers.py`.

---

## Task 1: Modelos de domínio (`app/core/models.py`)

**Files:**
- Create: `app/core/models.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/core/test_models.py`

- [ ] **Step 1: Criar estrutura de testes**

```bash
mkdir -p tests/core tests/services/notificacao tests/storage
touch tests/__init__.py tests/core/__init__.py tests/services/__init__.py tests/services/notificacao/__init__.py tests/storage/__init__.py
```

- [ ] **Step 2: Escrever o teste**

`tests/core/test_models.py`:
```python
from app.core.models import Execucao, DadoCorte, Evento


def test_execucao_fields():
    e = Execucao(
        id="abc",
        processadora="consigfacil",
        executada_em="2026-04-29T08:00:00",
        status="ok",
        total_convenios=3,
        success_count=3,
        error_count=0,
    )
    assert e.id == "abc"
    assert e.processadora == "consigfacil"
    assert e.status == "ok"
    assert e.total_convenios == 3


def test_dado_corte_campos_opcionais_podem_ser_none():
    d = DadoCorte(
        id="d1",
        execucao_id="exec1",
        convenio_key="belterra",
        convenio_nome=None,
        folha=None,
        mes_atual=None,
        data_corte=None,
        coletado_em="2026-04-29T08:00:00",
    )
    assert d.folha is None
    assert d.data_corte is None


def test_evento_fields_data_corte_alterada():
    e = Evento(
        id="e1",
        tipo="data_corte_alterada",
        processadora="consigfacil",
        convenio_key="belterra",
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior="10/05/2026",
        data_corte_nova="08/05/2026",
    )
    assert e.data_corte_anterior == "10/05/2026"
    assert e.data_corte_nova == "08/05/2026"


def test_evento_registro_novo_anterior_e_none():
    e = Evento(
        id="e2",
        tipo="registro_novo",
        processadora="consigfacil",
        convenio_key="belterra",
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior=None,
        data_corte_nova="10/05/2026",
    )
    assert e.data_corte_anterior is None
    assert e.data_corte_nova == "10/05/2026"
```

- [ ] **Step 3: Executar para confirmar FAIL**

```bash
pytest tests/core/test_models.py -v
```
Esperado: `ModuleNotFoundError: No module named 'app.core.models'`

- [ ] **Step 4: Implementar `app/core/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Execucao:
    id: str
    processadora: str
    executada_em: str
    status: str
    total_convenios: int
    success_count: int
    error_count: int


@dataclass
class DadoCorte:
    id: str
    execucao_id: str
    convenio_key: str
    convenio_nome: str | None
    folha: str | None
    mes_atual: str | None
    data_corte: str | None
    coletado_em: str


@dataclass
class Evento:
    id: str
    tipo: str
    processadora: str
    convenio_key: str
    execucao_id: str
    detectado_em: str
    folha: str | None
    mes_atual: str | None
    data_corte_anterior: str | None
    data_corte_nova: str | None
```

- [ ] **Step 5: Executar para confirmar PASS**

```bash
pytest tests/core/test_models.py -v
```
Esperado: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add app/core/models.py tests/core/test_models.py tests/__init__.py tests/core/__init__.py tests/services/__init__.py tests/services/notificacao/__init__.py tests/storage/__init__.py
git commit -m "feat: add domain models Execucao, DadoCorte, Evento"
```

---

## Task 2: Atualizar enums (`app/core/enums.py`)

**Files:**
- Modify: `app/core/enums.py`

- [ ] **Step 1: Escrever o teste**

Adicionar em `tests/core/test_models.py`:
```python
from app.core.enums import EventoTipo


def test_evento_tipo_valores():
    assert EventoTipo.DATA_CORTE_ALTERADA == "data_corte_alterada"
    assert EventoTipo.REGISTRO_NOVO == "registro_novo"
    assert EventoTipo.REGISTRO_NAO_ENCONTRADO == "registro_nao_encontrado"
    assert EventoTipo.ERRO_COLETA == "erro_coleta"
```

- [ ] **Step 2: Executar para confirmar FAIL**

```bash
pytest tests/core/test_models.py::test_evento_tipo_valores -v
```
Esperado: `ImportError` ou `AttributeError`

- [ ] **Step 3: Substituir conteúdo de `app/core/enums.py`**

```python
from enum import Enum


class AuthType(str, Enum):
    CERTIFICATE = "certificate"
    LOGIN_PASSWORD = "login_password"


class CollectionStatus(str, Enum):
    OK = "ok"
    ERROR = "erro"
    PARTIAL_SUCCESS = "partial_success"


class EventoTipo(str, Enum):
    DATA_CORTE_ALTERADA = "data_corte_alterada"
    REGISTRO_NOVO = "registro_novo"
    REGISTRO_NAO_ENCONTRADO = "registro_nao_encontrado"
    ERRO_COLETA = "erro_coleta"
```

- [ ] **Step 4: Executar para confirmar PASS**

```bash
pytest tests/core/test_models.py -v
```
Esperado: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add app/core/enums.py tests/core/test_models.py
git commit -m "feat: add EventoTipo enum with 4 types"
```

---

## Task 3: Interfaces de repositório (`app/storage/repository.py`)

**Files:**
- Rewrite: `app/storage/repository.py`

- [ ] **Step 1: Substituir `app/storage/repository.py`**

Não há testes diretos de ABC — a conformidade é testada nas implementações (Task 4). Substituir o arquivo:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models import Execucao, DadoCorte, Evento


class ExecucaoRepository(ABC):
    @abstractmethod
    def salvar(self, execucao: Execucao) -> None: ...

    @abstractmethod
    def buscar_ultima_ok(self, processadora: str) -> Execucao | None: ...

    @abstractmethod
    def listar(self, processadora: str) -> list[Execucao]: ...


class DadosCorteRepository(ABC):
    @abstractmethod
    def salvar_lote(self, dados: list[DadoCorte]) -> None: ...

    @abstractmethod
    def buscar_por_execucao(self, execucao_id: str) -> list[DadoCorte]: ...


class EventoRepository(ABC):
    @abstractmethod
    def salvar_lote(self, eventos: list[Evento]) -> None: ...
```

- [ ] **Step 2: Verificar que o projeto ainda importa corretamente**

```bash
python -c "from app.storage.repository import ExecucaoRepository, DadosCorteRepository, EventoRepository; print('ok')"
```
Esperado: `ok`

- [ ] **Step 3: Commit**

```bash
git add app/storage/repository.py
git commit -m "feat: redesign storage repository interfaces as domain-oriented ABCs"
```

---

## Task 4: Implementação file storage (`app/storage/file_storage.py`)

**Files:**
- Rewrite: `app/storage/file_storage.py`
- Create: `tests/storage/test_file_storage.py`

- [ ] **Step 1: Escrever os testes**

`tests/storage/test_file_storage.py`:
```python
import pytest
from app.core.models import Execucao, DadoCorte, Evento
from app.storage.file_storage import (
    FileExecucaoRepository,
    FileDadosCorteRepository,
    FileEventoRepository,
)


@pytest.fixture
def base(tmp_path):
    return str(tmp_path)


# --- ExecucaoRepository ---

def test_execucao_salvar_e_listar(base):
    repo = FileExecucaoRepository(base)
    e = Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    )
    repo.salvar(e)
    resultado = repo.listar("consigfacil")
    assert len(resultado) == 1
    assert resultado[0].id == "exec1"
    assert resultado[0].status == "ok"


def test_buscar_ultima_ok_retorna_none_se_vazio(base):
    repo = FileExecucaoRepository(base)
    assert repo.buscar_ultima_ok("consigfacil") is None


def test_buscar_ultima_ok_ignora_execucoes_com_erro(base):
    repo = FileExecucaoRepository(base)
    e_ok = Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T07:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    )
    e_erro = Execucao(
        id="exec2", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="erro",
        total_convenios=3, success_count=0, error_count=3,
    )
    repo.salvar(e_ok)
    repo.salvar(e_erro)
    ultima = repo.buscar_ultima_ok("consigfacil")
    assert ultima is not None
    assert ultima.id == "exec1"


def test_listar_ordena_mais_recente_primeiro(base):
    repo = FileExecucaoRepository(base)
    repo.salvar(Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-28T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    ))
    repo.salvar(Execucao(
        id="exec2", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    ))
    resultado = repo.listar("consigfacil")
    assert resultado[0].id == "exec2"


# --- DadosCorteRepository ---

def test_dados_corte_salvar_e_buscar(base):
    repo = FileDadosCorteRepository(base)
    dados = [
        DadoCorte(
            id="d1", execucao_id="exec1", convenio_key="belterra",
            convenio_nome="Belterra", folha="FOLHA 02", mes_atual="02/2026",
            data_corte="10/05/2026", coletado_em="2026-04-29T08:00:00",
        ),
    ]
    repo.salvar_lote(dados)
    resultado = repo.buscar_por_execucao("exec1")
    assert len(resultado) == 1
    assert resultado[0].data_corte == "10/05/2026"
    assert resultado[0].convenio_key == "belterra"


def test_dados_corte_buscar_inexistente_retorna_lista_vazia(base):
    repo = FileDadosCorteRepository(base)
    assert repo.buscar_por_execucao("nao-existe") == []


def test_dados_corte_salvar_lote_vazio_nao_falha(base):
    repo = FileDadosCorteRepository(base)
    repo.salvar_lote([])  # não deve levantar exceção


# --- EventoRepository ---

def test_evento_salvar_lote(base):
    repo = FileEventoRepository(base)
    eventos = [
        Evento(
            id="e1", tipo="data_corte_alterada", processadora="consigfacil",
            convenio_key="belterra", execucao_id="exec1",
            detectado_em="2026-04-29T08:00:00", folha="FOLHA 02",
            mes_atual="02/2026", data_corte_anterior="10/05/2026",
            data_corte_nova="08/05/2026",
        ),
    ]
    repo.salvar_lote(eventos)  # não deve levantar exceção


def test_evento_salvar_lote_vazio_nao_falha(base):
    repo = FileEventoRepository(base)
    repo.salvar_lote([])
```

- [ ] **Step 2: Executar para confirmar FAIL**

```bash
pytest tests/storage/test_file_storage.py -v
```
Esperado: `ImportError` — classes não existem ainda.

- [ ] **Step 3: Implementar `app/storage/file_storage.py`**

```python
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

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
```

- [ ] **Step 4: Executar para confirmar PASS**

```bash
pytest tests/storage/test_file_storage.py -v
```
Esperado: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add app/storage/repository.py app/storage/file_storage.py tests/storage/test_file_storage.py tests/storage/__init__.py
git commit -m "feat: implement file-based repositories for Execucao, DadosCorte, Evento"
```

---

## Task 5: ComparadorService (`app/services/comparador_service.py`)

**Files:**
- Rewrite: `app/services/comparador_service.py`
- Create: `tests/services/test_comparador_service.py`

- [ ] **Step 1: Escrever os testes**

`tests/services/test_comparador_service.py`:
```python
from app.services.comparador_service import ComparadorService
from app.core.models import DadoCorte
from app.core.enums import EventoTipo


def _dado(convenio_key: str, folha: str, mes_atual: str, data_corte: str, execucao_id: str = "exec1") -> DadoCorte:
    return DadoCorte(
        id="id", execucao_id=execucao_id, convenio_key=convenio_key,
        convenio_nome=None, folha=folha, mes_atual=mes_atual,
        data_corte=data_corte, coletado_em="2026-04-29T08:00:00",
    )


def test_detecta_mudanca_de_data():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "08/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.DATA_CORTE_ALTERADA
    assert eventos[0].data_corte_anterior == "10/05/2026"
    assert eventos[0].data_corte_nova == "08/05/2026"
    assert eventos[0].convenio_key == "belterra"


def test_sem_mudanca_nao_gera_evento():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert eventos == []


def test_detecta_registro_novo():
    anterior = []
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.REGISTRO_NOVO
    assert eventos[0].data_corte_anterior is None
    assert eventos[0].data_corte_nova == "10/05/2026"


def test_detecta_registro_nao_encontrado():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = []
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.REGISTRO_NAO_ENCONTRADO
    assert eventos[0].data_corte_anterior == "10/05/2026"
    assert eventos[0].data_corte_nova is None


def test_primeira_execucao_gera_apenas_registros_novos():
    atual = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),
        _dado("maranhao", "FOLHA 02", "02/2026", "12/05/2026"),
    ]
    eventos = ComparadorService().comparar("consigfacil", "exec1", [], atual)
    assert len(eventos) == 2
    assert all(e.tipo == EventoTipo.REGISTRO_NOVO for e in eventos)


def test_chave_inclui_convenio_key_para_evitar_colisao():
    # belterra e maranhao com mesma folha+mes mas dados corte diferentes
    anterior = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),
        _dado("maranhao", "FOLHA 02", "02/2026", "12/05/2026"),
    ]
    atual = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),  # sem mudança
        _dado("maranhao", "FOLHA 02", "02/2026", "09/05/2026"),  # mudou
    ]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.DATA_CORTE_ALTERADA
    assert eventos[0].convenio_key == "maranhao"
```

- [ ] **Step 2: Executar para confirmar FAIL**

```bash
pytest tests/services/test_comparador_service.py -v
```
Esperado: `ImportError` — `ComparadorService` não existe ainda.

- [ ] **Step 3: Implementar `app/services/comparador_service.py`**

```python
from __future__ import annotations

import uuid

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Evento
from app.services.storage_helpers import now_iso


class ComparadorService:
    def comparar(
        self,
        processadora: str,
        execucao_id: str,
        anteriores: list[DadoCorte],
        atuais: list[DadoCorte],
    ) -> list[Evento]:
        eventos: list[Evento] = []
        agora = now_iso()

        mapa_anterior = {self._chave(d): d for d in anteriores}
        mapa_atual = {self._chave(d): d for d in atuais}

        for chave, atual in mapa_atual.items():
            if chave not in mapa_anterior:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.REGISTRO_NOVO,
                    processadora=processadora,
                    convenio_key=atual.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=atual.folha,
                    mes_atual=atual.mes_atual,
                    data_corte_anterior=None,
                    data_corte_nova=atual.data_corte,
                ))
            elif mapa_anterior[chave].data_corte != atual.data_corte:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.DATA_CORTE_ALTERADA,
                    processadora=processadora,
                    convenio_key=atual.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=atual.folha,
                    mes_atual=atual.mes_atual,
                    data_corte_anterior=mapa_anterior[chave].data_corte,
                    data_corte_nova=atual.data_corte,
                ))

        for chave, anterior in mapa_anterior.items():
            if chave not in mapa_atual:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.REGISTRO_NAO_ENCONTRADO,
                    processadora=processadora,
                    convenio_key=anterior.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=anterior.folha,
                    mes_atual=anterior.mes_atual,
                    data_corte_anterior=anterior.data_corte,
                    data_corte_nova=None,
                ))

        return eventos

    @staticmethod
    def _chave(dado: DadoCorte) -> str:
        return f"{dado.convenio_key}|{(dado.folha or '').strip()}|{(dado.mes_atual or '').strip()}"
```

- [ ] **Step 4: Executar para confirmar PASS**

```bash
pytest tests/services/test_comparador_service.py -v
```
Esperado: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/comparador_service.py tests/services/test_comparador_service.py tests/services/__init__.py
git commit -m "feat: implement ComparadorService with typed Evento output"
```

---

## Task 6: Camada de notificação (`app/services/notificacao/`)

**Files:**
- Create: `app/services/notificacao/__init__.py`
- Create: `app/services/notificacao/base.py`
- Create: `app/services/notificacao/digest_builder.py`
- Create: `app/services/notificacao/smtp.py`
- Create: `tests/services/notificacao/test_digest_builder.py`

- [ ] **Step 1: Escrever os testes do DigestBuilder**

`tests/services/notificacao/test_digest_builder.py`:
```python
from app.services.notificacao.digest_builder import DigestBuilder
from app.core.models import Evento
from app.core.enums import EventoTipo


def _mudanca(convenio_key: str, antes: str, depois: str) -> Evento:
    return Evento(
        id="e1",
        tipo=EventoTipo.DATA_CORTE_ALTERADA,
        processadora="consigfacil",
        convenio_key=convenio_key,
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior=antes,
        data_corte_nova=depois,
    )


def test_assunto_singular():
    assunto, _ = DigestBuilder.build("consigfacil", [_mudanca("belterra", "10/05/2026", "08/05/2026")])
    assert "1 alteração" in assunto
    assert "consigfacil" in assunto


def test_assunto_plural():
    mudancas = [
        _mudanca("belterra", "10/05/2026", "08/05/2026"),
        _mudanca("maranhao", "12/05/2026", "10/05/2026"),
    ]
    assunto, _ = DigestBuilder.build("consigfacil", mudancas)
    assert "2 alterações" in assunto


def test_corpo_contem_dados_da_mudanca():
    mudancas = [_mudanca("belterra", "10/05/2026", "08/05/2026")]
    _, corpo = DigestBuilder.build("consigfacil", mudancas)
    assert "belterra" in corpo
    assert "10/05/2026" in corpo
    assert "08/05/2026" in corpo


def test_corpo_e_html():
    _, corpo = DigestBuilder.build("consigfacil", [_mudanca("b", "x", "y")])
    assert "<html" in corpo.lower() or "<table" in corpo.lower()
```

- [ ] **Step 2: Executar para confirmar FAIL**

```bash
pytest tests/services/notificacao/test_digest_builder.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Criar `app/services/notificacao/__init__.py`** (vazio)

```bash
touch app/services/notificacao/__init__.py
```

- [ ] **Step 4: Criar `app/services/notificacao/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificadorBase(ABC):
    @abstractmethod
    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None: ...
```

- [ ] **Step 5: Criar `app/services/notificacao/digest_builder.py`**

```python
from __future__ import annotations

from app.core.models import Evento


class DigestBuilder:
    @staticmethod
    def build(processadora: str, mudancas: list[Evento]) -> tuple[str, str]:
        n = len(mudancas)
        plural = "alteração" if n == 1 else "alterações"
        assunto = f"[Alerta] Mudança de data de corte — {processadora} ({n} {plural})"

        linhas = "".join(
            f"""
            <tr>
                <td style="padding:6px 12px">{e.convenio_key}</td>
                <td style="padding:6px 12px">{e.folha or '-'}</td>
                <td style="padding:6px 12px">{e.mes_atual or '-'}</td>
                <td style="padding:6px 12px">{e.data_corte_anterior or '-'}</td>
                <td style="padding:6px 12px"><strong>{e.data_corte_nova or '-'}</strong></td>
            </tr>"""
            for e in mudancas
        )

        corpo = f"""
        <html>
        <body style="font-family:sans-serif">
            <h2>Mudança de data de corte detectada</h2>
            <p><strong>Processadora:</strong> {processadora}</p>
            <table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
                <thead>
                    <tr style="background:#f0f0f0">
                        <th style="padding:6px 12px">Convênio</th>
                        <th style="padding:6px 12px">Folha</th>
                        <th style="padding:6px 12px">Mês</th>
                        <th style="padding:6px 12px">Antes</th>
                        <th style="padding:6px 12px">Depois</th>
                    </tr>
                </thead>
                <tbody>{linhas}</tbody>
            </table>
        </body>
        </html>
        """

        return assunto, corpo
```

- [ ] **Step 6: Criar `app/services/notificacao/smtp.py`**

```python
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.notificacao.base import NotificadorBase


class EmailSMTPNotificador(NotificadorBase):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._use_tls = use_tls

    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = self._user
        msg["To"] = ", ".join(destinatarios)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls(context=context)
            smtp.login(self._user, self._password)
            smtp.sendmail(self._user, destinatarios, msg.as_string())
```

- [ ] **Step 7: Executar para confirmar PASS**

```bash
pytest tests/services/notificacao/test_digest_builder.py -v
```
Esperado: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add app/services/notificacao/ tests/services/notificacao/
git commit -m "feat: add notification layer with NotificadorBase, EmailSMTPNotificador, DigestBuilder"
```

---

## Task 7: Atualizar settings (`app/core/settings.py`)

**Files:**
- Modify: `app/core/settings.py`

- [ ] **Step 1: Substituir `app/core/settings.py`**

```python
import os

from dotenv import load_dotenv

load_dotenv(override=True)


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    HEADLESS: bool = _bool(os.getenv("HEADLESS"), False)
    TIMEOUT_MS: int = int(os.getenv("TIMEOUT_MS", "180000"))
    CHROME_CHANNEL: str = os.getenv("CHROME_CHANNEL", "chrome")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "data")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _bool(os.getenv("SMTP_USE_TLS"), True)
    NOTIFICACAO_DESTINATARIOS: list[str] = [
        e.strip()
        for e in os.getenv("NOTIFICACAO_DESTINATARIOS", "").split(",")
        if e.strip()
    ]


settings = Settings()
```

- [ ] **Step 2: Verificar import**

```bash
python -c "from app.core.settings import settings; print(settings.SMTP_HOST, settings.SMTP_PORT)"
```
Esperado: ` 587` (valores vazios/default)

- [ ] **Step 3: Commit**

```bash
git add app/core/settings.py
git commit -m "feat: add SMTP settings to Settings class"
```

---

## Task 8: ColetaOrchestrator (`app/services/orchestrator.py`)

**Files:**
- Create: `app/services/orchestrator.py`
- Create: `tests/services/test_orchestrator.py`

- [ ] **Step 1: Escrever os testes**

`tests/services/test_orchestrator.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Execucao
from app.services.comparador_service import ComparadorService
from app.services.orchestrator import ColetaOrchestrator


def _execucao_ok(id: str = "exec-anterior") -> Execucao:
    return Execucao(
        id=id, processadora="consigfacil",
        executada_em="2026-04-28T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    )


def _dado(data_corte: str, execucao_id: str = "exec-anterior") -> DadoCorte:
    return DadoCorte(
        id="d-old", execucao_id=execucao_id, convenio_key="belterra",
        convenio_nome="Belterra", folha="FOLHA 02", mes_atual="02/2026",
        data_corte=data_corte, coletado_em="2026-04-28T08:00:00",
    )


RESULTADO_LOTE_OK = {
    "processadora": "consigfacil",
    "status": "ok",
    "total_convenios": 1,
    "success_count": 1,
    "error_count": 0,
    "records": [
        {
            "convenio_key": "belterra",
            "convenio_nome": "Belterra",
            "folha": "FOLHA 02",
            "mes_atual": "02/2026",
            "data_corte": "10/05/2026",
        }
    ],
}


@pytest.fixture
def orch():
    execucao_repo = MagicMock()
    dados_repo = MagicMock()
    evento_repo = MagicMock()
    notificador = MagicMock()
    execucao_repo.buscar_ultima_ok.return_value = None
    dados_repo.buscar_por_execucao.return_value = []
    return (
        ColetaOrchestrator(
            execucao_repo=execucao_repo,
            dados_repo=dados_repo,
            evento_repo=evento_repo,
            comparador=ComparadorService(),
            notificador=notificador,
            destinatarios=["analista@empresa.com"],
        ),
        execucao_repo,
        dados_repo,
        evento_repo,
        notificador,
    )


def test_primeira_execucao_nao_envia_email(orch):
    o, _, _, _, notificador = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        execucao = o.executar("consigfacil")
    assert execucao.status == "ok"
    notificador.enviar.assert_not_called()


def test_mudanca_dispara_email(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("12/05/2026")]  # data diferente
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    notificador.enviar.assert_called_once()


def test_sem_mudanca_nao_envia_email(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("10/05/2026")]  # mesma data
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    notificador.enviar.assert_not_called()


def test_falha_email_nao_propaga_excecao(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    notificador.enviar.side_effect = Exception("SMTP error")
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("12/05/2026")]
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        execucao = o.executar("consigfacil")  # não deve levantar
    assert execucao is not None


def test_execucao_salva_com_status_correto(orch):
    o, execucao_repo, _, _, _ = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    execucao_repo.salvar.assert_called_once()
    execucao_salva = execucao_repo.salvar.call_args[0][0]
    assert execucao_salva.status == "ok"
    assert execucao_salva.processadora == "consigfacil"


def test_dados_carregados_antes_de_salvar_nova_execucao(orch):
    """Garante que buscar_ultima_ok é chamado antes de salvar a nova execução."""
    o, execucao_repo, dados_repo, _, _ = orch
    call_order = []
    execucao_repo.buscar_ultima_ok.side_effect = lambda p: call_order.append("buscar") or None
    execucao_repo.salvar.side_effect = lambda e: call_order.append("salvar")
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    assert call_order.index("buscar") < call_order.index("salvar")
```

- [ ] **Step 2: Executar para confirmar FAIL**

```bash
pytest tests/services/test_orchestrator.py -v
```
Esperado: `ImportError: No module named 'app.services.orchestrator'`

- [ ] **Step 3: Implementar `app/services/orchestrator.py`**

```python
from __future__ import annotations

import uuid

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Execucao
from app.services.coleta_service import executar_coleta_lote
from app.services.comparador_service import ComparadorService
from app.services.notificacao.base import NotificadorBase
from app.services.notificacao.digest_builder import DigestBuilder
from app.services.storage_helpers import now_iso
from app.storage.repository import (
    DadosCorteRepository,
    EventoRepository,
    ExecucaoRepository,
)


class ColetaOrchestrator:
    def __init__(
        self,
        execucao_repo: ExecucaoRepository,
        dados_repo: DadosCorteRepository,
        evento_repo: EventoRepository,
        comparador: ComparadorService,
        notificador: NotificadorBase,
        destinatarios: list[str],
    ) -> None:
        self._execucao_repo = execucao_repo
        self._dados_repo = dados_repo
        self._evento_repo = evento_repo
        self._comparador = comparador
        self._notificador = notificador
        self._destinatarios = destinatarios

    def executar(self, processadora: str) -> Execucao:
        # 1. Carregar dados anteriores ANTES de salvar qualquer coisa
        ultima_ok = self._execucao_repo.buscar_ultima_ok(processadora)
        dados_anteriores = (
            self._dados_repo.buscar_por_execucao(ultima_ok.id) if ultima_ok else []
        )

        # 2. Rodar scrapers
        resultado_lote = executar_coleta_lote(processadora)

        # 3. Salvar execução
        execucao = Execucao(
            id=str(uuid.uuid4()),
            processadora=processadora,
            executada_em=now_iso(),
            status=resultado_lote["status"],
            total_convenios=resultado_lote["total_convenios"],
            success_count=resultado_lote["success_count"],
            error_count=resultado_lote["error_count"],
        )
        self._execucao_repo.salvar(execucao)

        # 4. Converter e salvar dados coletados com sucesso
        dados_atuais = [
            DadoCorte(
                id=str(uuid.uuid4()),
                execucao_id=execucao.id,
                convenio_key=r["convenio_key"],
                convenio_nome=r.get("convenio_nome"),
                folha=r.get("folha"),
                mes_atual=r.get("mes_atual"),
                data_corte=r.get("data_corte"),
                coletado_em=now_iso(),
            )
            for r in resultado_lote.get("records", [])
        ]
        self._dados_repo.salvar_lote(dados_atuais)

        # 5. Comparar e persistir eventos
        eventos = self._comparador.comparar(
            processadora=processadora,
            execucao_id=execucao.id,
            anteriores=dados_anteriores,
            atuais=dados_atuais,
        )
        self._evento_repo.salvar_lote(eventos)

        # 6. Notificar mudanças de data de corte
        mudancas = [e for e in eventos if e.tipo == EventoTipo.DATA_CORTE_ALTERADA]
        if mudancas and self._destinatarios:
            assunto, corpo = DigestBuilder.build(processadora, mudancas)
            try:
                self._notificador.enviar(assunto, self._destinatarios, corpo)
            except Exception as exc:
                print(f"[orchestrator] Falha ao enviar notificação: {exc}")

        return execucao
```

- [ ] **Step 4: Executar para confirmar PASS**

```bash
pytest tests/services/test_orchestrator.py -v
```
Esperado: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/orchestrator.py tests/services/test_orchestrator.py
git commit -m "feat: implement ColetaOrchestrator with full collect-compare-notify pipeline"
```

---

## Task 9: Atualizar API e remover arquivos obsoletos (`app/api/main.py`)

**Files:**
- Rewrite: `app/api/main.py`
- Delete: `app/services/collector_service.py`
- Delete: `app/services/comparator.py`
- Delete: `app/services/events.py`
- Delete: `app/services/alert.py`

- [ ] **Step 1: Reescrever `app/api/main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notificacao.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
)

app = FastAPI(title="Pipeline Corte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_orchestrator() -> ColetaOrchestrator:
    return ColetaOrchestrator(
        execucao_repo=FileExecucaoRepository(settings.STORAGE_PATH),
        dados_repo=FileDadosCorteRepository(settings.STORAGE_PATH),
        evento_repo=FileEventoRepository(settings.STORAGE_PATH),
        comparador=ComparadorService(),
        notificador=EmailSMTPNotificador(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        ),
        destinatarios=settings.NOTIFICACAO_DESTINATARIOS,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/coletas/{processadora}/executar")
def executar_coleta(processadora: str) -> dict:
    try:
        execucao = _build_orchestrator().executar(processadora)
        return {
            "id": execucao.id,
            "processadora": execucao.processadora,
            "status": execucao.status,
            "executada_em": execucao.executada_em,
            "total_convenios": execucao.total_convenios,
            "success_count": execucao.success_count,
            "error_count": execucao.error_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coletas/{processadora}/execucoes")
def listar_execucoes(processadora: str) -> list[dict]:
    repo = FileExecucaoRepository(settings.STORAGE_PATH)
    return [e.__dict__ for e in repo.listar(processadora)]


@app.get("/coletas/{processadora}/dados")
def obter_dados_atuais(processadora: str) -> list[dict]:
    execucao_repo = FileExecucaoRepository(settings.STORAGE_PATH)
    dados_repo = FileDadosCorteRepository(settings.STORAGE_PATH)
    ultima = execucao_repo.buscar_ultima_ok(processadora)
    if not ultima:
        return []
    return [d.__dict__ for d in dados_repo.buscar_por_execucao(ultima.id)]
```

- [ ] **Step 2: Deletar arquivos obsoletos**

```bash
git rm app/services/collector_service.py app/services/comparator.py app/services/events.py app/services/alert.py
```

- [ ] **Step 3: Verificar que a API sobe corretamente**

```bash
python -c "from app.api.main import app; print('API ok')"
```
Esperado: `API ok`

- [ ] **Step 4: Rodar todos os testes para confirmar nenhuma regressão**

```bash
pytest tests/ -v
```
Esperado: todos os testes passando, nenhum `ImportError` relacionado aos arquivos deletados.

- [ ] **Step 5: Commit final**

```bash
git add app/api/main.py
git commit -m "feat: wire orchestrator into API, remove obsolete collector/comparator/events/alert modules"
```

---

## Verificação final

- [ ] **Rodar suite completa**

```bash
pytest tests/ -v --tb=short
```
Esperado: todos os testes passando.

- [ ] **Smoke test da API**

```bash
uvicorn app.api.main:app --reload
# Em outro terminal:
curl http://localhost:8000/health
```
Esperado: `{"status":"ok"}`
