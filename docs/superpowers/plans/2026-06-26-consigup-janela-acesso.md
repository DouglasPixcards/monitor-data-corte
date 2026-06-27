# Janela de acesso de coleta do ConsigUp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Não tentar coletar o ConsigUp fora da janela 08:00–16:45 (America/Sao_Paulo) e tratar o skip como pendência de rodapé, não como falha.

**Architecture:** A janela é checada no funil único de coleta (`executar_coleta_lote`), antes do login, cobrindo tentativa inicial, retry de 60min e on-demand. O skip vira um desfecho `fora_janela` (≠ ok, ≠ erro) que não conta como falha, não dispara retry e cai no rodapé do e-mail.

**Tech Stack:** Python 3.14, pytest, `zoneinfo` (fallback offset fixo).

## Global Constraints

- Janela: **08:00–17:00 America/Sao_Paulo**, corte efetivo **16:45** (margem 15 min). **Dias úteis (seg–sex); fim de semana não coleta.**
- Escopo: **somente `consigup`**. Outras processadoras nunca são puladas.
- **Não** alterar lógica de retry nem `COLETA_HORARIO`.
- Fora da janela: **não tocar o portal** (não construir auth/scraper, não logar).
- `fora_janela` é desfecho distinto: não conta como sucesso nem como `error_count`.
- Fallback de fuso: se `zoneinfo("America/Sao_Paulo")` falhar (tzdata ausente), usar `timezone(-03:00)`.

---

### Task 1: Janela helper + status de enum

**Files:**
- Create: `app/services/janela_coleta.py`
- Modify: `app/core/enums.py` (classe `CollectionStatus`)
- Test: `tests/services/test_janela_coleta.py`

**Interfaces:**
- Produces: `dentro_da_janela_consigup(agora: datetime | None = None) -> bool`; `PROCESSADORA: str = "consigup"`; `_agora_local() -> datetime` (patchável); `CollectionStatus.FORA_JANELA == "fora_janela"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_janela_coleta.py
from datetime import datetime
import app.services.janela_coleta as jc


def _dt(h, m):  # naive = hora-de-parede local; basta para a lógica de janela
    return datetime(2026, 6, 26, h, m)


def test_meio_da_tarde_dentro():
    assert jc.dentro_da_janela_consigup(_dt(14, 0)) is True

def test_antes_das_8_fora():
    assert jc.dentro_da_janela_consigup(_dt(7, 59)) is False

def test_borda_16_44_dentro():
    assert jc.dentro_da_janela_consigup(_dt(16, 44)) is True

def test_borda_16_45_fora():  # margem de 15 min antes das 17h
    assert jc.dentro_da_janela_consigup(_dt(16, 45)) is False

def test_apos_17_fora():
    assert jc.dentro_da_janela_consigup(_dt(18, 30)) is False

def test_sabado_fora():  # 2026-06-27 = sábado
    assert jc.dentro_da_janela_consigup(datetime(2026, 6, 27, 14, 0)) is False

def test_domingo_fora():  # 2026-06-28 = domingo
    assert jc.dentro_da_janela_consigup(datetime(2026, 6, 28, 14, 0)) is False

def test_status_enum_fora_janela():
    from app.core.enums import CollectionStatus
    assert CollectionStatus.FORA_JANELA == "fora_janela"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_janela_coleta.py -q`
Expected: FAIL (`ModuleNotFoundError: app.services.janela_coleta`).

- [ ] **Step 3: Add the enum member**

In `app/core/enums.py`, dentro de `class CollectionStatus(str, Enum)`:

```python
class CollectionStatus(str, Enum):
    OK = "ok"
    ERROR = "erro"
    PARTIAL_SUCCESS = "partial_success"
    FORA_JANELA = "fora_janela"
```

- [ ] **Step 4: Create the helper**

```python
# app/services/janela_coleta.py
"""Janela de acesso de coleta do ConsigUp.

O portal ConsigUp (sistema.consigup.com.br) só permite acesso em horário
comercial (08:00–17:00, America/Sao_Paulo). Fora disso a coleta é PULADA —
não se toca o portal. Específico do consigup; não é um sistema genérico.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # tzdata ausente (ex.: Windows sem o pacote) → offset fixo
    _TZ = timezone(timedelta(hours=-3))

PROCESSADORA = "consigup"
JANELA_INICIO = time(8, 0)
JANELA_FIM = time(17, 0)
MARGEM_MIN = 15  # corte efetivo = 16:45


def _agora_local() -> datetime:
    """Hora atual no fuso do portal. Patchável nos testes."""
    return datetime.now(_TZ)


def _corte_efetivo() -> time:
    base = datetime(2000, 1, 1, JANELA_FIM.hour, JANELA_FIM.minute)
    return (base - timedelta(minutes=MARGEM_MIN)).time()


def dentro_da_janela_consigup(agora: datetime | None = None) -> bool:
    """True se ``agora`` está na janela: dia útil (seg–sex) e 08:00 ≤ hora < 16:45."""
    agora = agora if agora is not None else _agora_local()
    if agora.weekday() >= 5:  # 5=sábado, 6=domingo — fim de semana não coleta
        return False
    t = agora.time()
    return JANELA_INICIO <= t < _corte_efetivo()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_janela_coleta.py -q`
Expected: PASS (8 passed).

- [ ] **Step 6: Commit**

```bash
git add app/services/janela_coleta.py app/core/enums.py tests/services/test_janela_coleta.py
git commit -m "feat(consigup): janela de acesso (helper + status fora_janela)"
```

---

### Task 2: Pular o ConsigUp fora da janela em `executar_coleta_lote`

**Files:**
- Modify: `app/services/coleta_service.py` (`executar_coleta_lote`, `_calcular_status_lote`)
- Test: `tests/services/test_coleta_service_janela.py`

**Interfaces:**
- Consumes: `dentro_da_janela_consigup`, `PROCESSADORA` (Task 1); `CollectionStatus.FORA_JANELA`.
- Produces: resultado do lote com convênios `status="fora_janela"`; `lote["status"] == "fora_janela"` quando todos pulados; `lote["error_count"]` exclui `fora_janela`; novo `lote["fora_janela_count"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_coleta_service_janela.py
from unittest.mock import patch
from app.services.coleta_service import executar_coleta_lote

_CFG = {
    "processadoras": {"consigup": {"auth_type": "login_password", "selectors": {}}},
    "convenios": {"muana": {"processadora": "consigup", "nome": "PREF DE MUANA - PA",
                            "credential_env_key": "CONSIGUP_MUANA"}},
}


def _patches():
    return (
        patch("app.services.coleta_service.load_processadoras_config", return_value=_CFG),
        patch("app.services.coleta_service.build_auth_strategy"),
        patch("app.services.coleta_service.build_scraper"),
        patch("app.services.coleta_service.dentro_da_janela_consigup"),
    )


def test_fora_da_janela_pula_sem_tocar_portal():
    p_cfg, p_auth, p_scr, p_jan = _patches()
    with p_cfg, p_auth as auth, p_scr as scr, p_jan as jan:
        jan.return_value = False
        lote = executar_coleta_lote("consigup")
    conv = lote["convenios"][0]
    assert conv["status"] == "fora_janela"
    assert lote["status"] == "fora_janela"
    assert lote["error_count"] == 0
    assert lote["fora_janela_count"] == 1
    assert lote["success_count"] == 0
    auth.assert_not_called()   # não construiu credencial
    scr.assert_not_called()    # não tocou o portal


def test_dentro_da_janela_coleta_normal():
    p_cfg, p_auth, p_scr, p_jan = _patches()
    with p_cfg, p_auth, p_scr as scr, p_jan as jan:
        jan.return_value = True
        scr.return_value.run.return_value = {
            "status": "ok",
            "dados": [{"folha": "F", "mes_atual": "07/2026", "data_corte": "10/07/2026"}],
        }
        lote = executar_coleta_lote("consigup")
    assert lote["convenios"][0]["status"] == "ok"
    assert lote["fora_janela_count"] == 0
    scr.return_value.run.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_coleta_service_janela.py -q`
Expected: FAIL (`KeyError: 'fora_janela_count'` / status não é `fora_janela`).

- [ ] **Step 3: Add the import and the skip**

No topo de `app/services/coleta_service.py`, junto aos imports:

```python
from app.services.janela_coleta import PROCESSADORA as CONSIGUP, dentro_da_janela_consigup
```

Dentro do loop `for convenio_key, convenio_config in convenios_da_processadora.items():`, **logo após** a linha `known_failure = bool(...)` e **antes** do `if processadora_config.get("integration_type") == "api":`:

```python
        # Janela de acesso do ConsigUp: fora do horário, pula sem tocar o portal
        # (cobre tentativa inicial, retry de 60min e on-demand — todos passam aqui).
        if processadora_key == CONSIGUP and not dentro_da_janela_consigup():
            logger.info("[ConsigUp] %s fora da janela de acesso — coleta pulada nesta rodada.", convenio_key)
            resultados_convenios.append({
                "convenio_key": convenio_key,
                "convenio_nome": convenio_config.get("nome"),
                "status": "fora_janela",
                "records_count": 0,
                "erro": "[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada.",
                "dados": [],
                "known_failure": known_failure,
            })
            continue
```

- [ ] **Step 4: Update `_calcular_status_lote` and the return counts**

Substituir `_calcular_status_lote` por:

```python
def _calcular_status_lote(resultados_convenios: list[dict]) -> str:
    if not resultados_convenios:
        return CollectionStatus.ERROR

    total = len(resultados_convenios)
    fora = sum(1 for item in resultados_convenios if item["status"] == CollectionStatus.FORA_JANELA)
    if fora == total:
        return CollectionStatus.FORA_JANELA  # nenhum tocou o portal — não é falha

    considerados = total - fora
    sucessos = sum(1 for item in resultados_convenios if item["status"] == CollectionStatus.OK)
    if sucessos == considerados:
        return CollectionStatus.OK
    if sucessos == 0:
        return CollectionStatus.ERROR
    return CollectionStatus.PARTIAL_SUCCESS
```

No dict de retorno de `executar_coleta_lote`, trocar a linha de `error_count` e adicionar `fora_janela_count`:

```python
        "success_count": sum(1 for item in resultados_convenios if item["status"] == "ok"),
        "error_count": sum(1 for item in resultados_convenios if item["status"] not in ("ok", "fora_janela")),
        "fora_janela_count": sum(1 for item in resultados_convenios if item["status"] == "fora_janela"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_coleta_service_janela.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/services/coleta_service.py tests/services/test_coleta_service_janela.py
git commit -m "feat(consigup): pular coleta fora da janela sem tocar o portal"
```

---

### Task 3: Evento `fora_janela` (classificação + comparador + orchestrator)

**Files:**
- Modify: `app/services/erro_classifier.py` (`CATEGORIAS`, `CATEGORIA_FRASE`)
- Modify: `app/services/comparador_service.py` (`_comparar_status`)
- Modify: `app/services/orchestrator.py` (`coletar`: `status_atual` e `erros_convenios`)
- Test: `tests/services/test_comparador_service.py` (acrescentar)

**Interfaces:**
- Consumes: convênio com `status="fora_janela"` no lote (Task 2).
- Produces: evento `ERRO_COLETA` com `categoria="fora_janela"`, `subtipo="fora_janela"`; `CATEGORIA_FRASE["fora_janela"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_comparador_service.py  (acrescentar ao final)
from app.core.enums import EventoTipo
from app.services.comparador_service import ComparadorService


def test_fora_janela_gera_evento_de_rodape():
    eventos = ComparadorService().comparar(
        processadora="consigup", execucao_id="e1",
        anteriores=[], atuais=[],
        status_anterior={"muana": "coletado"},
        status_atual={"muana": {"status": "fora_janela",
                                "erro": "[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada.",
                                "known_failure": False, "records_count": 0,
                                "convenio_nome": "PREF DE MUANA - PA"}},
    )
    fj = [e for e in eventos if e.tipo == EventoTipo.ERRO_COLETA and e.categoria == "fora_janela"]
    assert len(fj) == 1
    assert fj[0].subtipo == "fora_janela"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_comparador_service.py::test_fora_janela_gera_evento_de_rodape -q`
Expected: FAIL (nenhum evento com categoria `fora_janela`).

- [ ] **Step 3: Add the category to `erro_classifier`**

Em `app/services/erro_classifier.py`, acrescentar `"fora_janela"` à tupla `CATEGORIAS` e ao dict `CATEGORIA_FRASE`:

```python
CATEGORIAS = (
    "auth_falhou",
    "rede",
    "fora_janela",
    "sem_dado",
    "timeout",
    "portal_mudou",
    "nao_executou",
    "falha_conhecida",
    "outro",
)

# em CATEGORIA_FRASE:
    "fora_janela": "fora da janela de acesso do portal — coleta adiada",
```

(`classificar_erro` não muda: a categoria é setada explicitamente pelo comparador.)

- [ ] **Step 4: Add the `fora_janela` branch in `_comparar_status`**

Em `app/services/comparador_service.py`, dentro de `_comparar_status`, logo após o bloco `if st == "ok": ... continue`:

```python
            # Pulado por janela de acesso — pendência informativa (rodapé).
            if st == "fora_janela":
                eventos.append(self._ev_status(
                    processadora, convenio_key, execucao_id, agora,
                    tipo=EventoTipo.ERRO_COLETA, categoria="fora_janela",
                    subtipo="fora_janela", detalhe=cur.get("erro"),
                ))
                continue
```

- [ ] **Step 5: Map `fora_janela` in `orchestrator.coletar`**

Em `app/services/orchestrator.py`, no loop `for c in resultado_lote.get("convenios", []):` (montagem de `status_atual`), trocar o `if/elif/else` por:

```python
            if c.get("status") == "fora_janela":
                efetivo = "fora_janela"
            elif c.get("status") != "ok":
                efetivo = "erro"
            elif ck in convs_com_dado:
                efetivo = "ok"
            else:
                efetivo = "sem_dado"
```

E na lista `erros_convenios`, trocar o filtro para não registrar `fora_janela` como erro:

```python
            if c.get("status") not in ("ok", "fora_janela")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/services/test_comparador_service.py -q`
Expected: PASS (incl. o novo teste).

- [ ] **Step 7: Commit**

```bash
git add app/services/erro_classifier.py app/services/comparador_service.py app/services/orchestrator.py tests/services/test_comparador_service.py
git commit -m "feat(consigup): evento fora_janela (classificacao + comparador + orchestrator)"
```

---

### Task 4: Renderizar `fora_janela` no rodapé do e-mail

**Files:**
- Modify: `app/services/notification/digest_builder.py` (`_categorizar`, `_montar_corpo`)
- Test: `tests/services/notificacao/test_digest_builder.py` (acrescentar)

**Interfaces:**
- Consumes: evento `ERRO_COLETA` `categoria="fora_janela"` (Task 3).
- Produces: subseção de rodapé "Fora da janela de acesso (coleta adiada)"; assunto **sem** `[Ação]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/notificacao/test_digest_builder.py  (acrescentar)
import uuid
from app.core.enums import EventoTipo
from app.core.models import Evento
from app.services.notification.digest_builder import DigestBuilder


def _ev_fora_janela():
    return Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consigup",
        convenio_key="muana", execucao_id="e1", detectado_em="2026-06-26T18:00:00",
        categoria="fora_janela", subtipo="fora_janela",
        detalhe="[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada.",
    )


def test_fora_janela_vai_pro_rodape_sem_acao():
    lote = {"processadora": "consigup", "total_convenios": 1, "success_count": 0,
            "convenios": [{"convenio_key": "muana", "convenio_nome": "PREF DE MUANA - PA"}]}
    assunto, corpo = DigestBuilder.build("consigup", [_ev_fora_janela()], lote)
    assert "Fora da janela de acesso" in corpo
    assert not assunto.startswith("[Ação]")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/services/notificacao/test_digest_builder.py::test_fora_janela_vai_pro_rodape_sem_acao -q`
Expected: FAIL (texto "Fora da janela de acesso" ausente no corpo).

- [ ] **Step 3: Group `fora_janela` in `_categorizar`**

Em `app/services/notification/digest_builder.py`, dentro de `_categorizar`, ajustar `reais` para excluir `fora_janela` e adicionar o grupo:

```python
    fora_janela = [e for e in falhas if e.categoria == "fora_janela"]
    reais = [e for e in falhas
             if e.categoria not in ("sem_dado", "nao_executou", "fora_janela")
             and e.subtipo != "conhecida"]
```

E acrescentar `"fora_janela": fora_janela` ao dict retornado.

- [ ] **Step 4: Render the footer subsection in `_montar_corpo`**

Em `_montar_corpo`, no bloco do rodapé (`rodape: list[str] = []`), acrescentar antes das "persistentes/conhecidas":

```python
    if cat["fora_janela"]:
        rodape.append(_secao_falhas("Fora da janela de acesso (coleta adiada)", cat["fora_janela"], rotulo))
```

(`_precisa_acao` já não inclui `fora_janela`, então o assunto não recebe `[Ação]`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/services/notificacao/test_digest_builder.py -q`
Expected: PASS (incl. o novo teste).

- [ ] **Step 6: Run the full suite**

Run: `./env/Scripts/python.exe -m pytest -q`
Expected: PASS (96 anteriores + novos; 10 skipped). Nenhuma regressão.

- [ ] **Step 7: Commit**

```bash
git add app/services/notification/digest_builder.py tests/services/notificacao/test_digest_builder.py
git commit -m "feat(consigup): renderizar fora_janela no rodape do e-mail"
```

---

## Verification (end-to-end, sem tocar o portal)

1. `./env/Scripts/python.exe -m pytest -q` → tudo verde.
2. Smoke do desfecho fora da janela, com relógio às 18h (patch), sem rede:
   ```python
   from unittest.mock import patch
   from app.services.coleta_service import executar_coleta_lote
   with patch("app.services.coleta_service.dentro_da_janela_consigup", return_value=False):
       # (com load_processadoras_config/build_scraper mockados como nos testes)
       ...  # asserta status == "fora_janela", scraper não chamado
   ```
3. Confirmar fuso no Windows: `./env/Scripts/python.exe -c "from app.services.janela_coleta import dentro_da_janela_consigup; print('ok')"` — se `zoneinfo` falhar por tzdata, o fallback `-03:00` cobre.
4. **NÃO** rodar contra `sistema.consigup.com.br` (credencial em rotação).

## Notas

- A regra cobre on-demand (API) também, por estar no funil único. Se isso não for desejado para "coletar agora", restringir ao caminho agendado é uma mudança pequena (passar uma flag ao `executar_coleta_lote`) — fora do escopo atual.
- **Fim de semana:** não coleta (sáb/dom → `fora_janela`), já incluído no helper (`weekday() >= 5`).
</content>
