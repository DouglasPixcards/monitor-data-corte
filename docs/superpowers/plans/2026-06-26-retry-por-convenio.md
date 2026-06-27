# Retry por-convênio — Implementation Plan

**Goal:** No caminho agendado, re-coletar só os convênios técnicos que falharam (um a um) e fundir no lote, em vez de re-rodar o lote inteiro.

**Tech:** Python 3.14, pytest. Mudança em 2 arquivos + testes.

## Global Constraints
- Definição de "técnico retentável" **inalterada** (`_erros_tecnicos_retentaveis`): status ≠ ok, ≠ fora_janela, não known_failure, não auth_falhou.
- **Teto = 2** rodadas; **só caminho agendado** (`retentar_tecnico=True`); **take-last** por convênio.
- `executar_coleta_lote` mantém comportamento idêntico (só extrai helper).

---

### Task 1: extrair `resumir_lote` em coleta_service

**Files:** Modify `app/services/coleta_service.py`; Test `tests/services/test_coleta_service_resumo.py`

- [ ] **Step 1 — teste (falha)**
```python
# tests/services/test_coleta_service_resumo.py
from app.services.coleta_service import resumir_lote

def _c(key, status):
    return {"convenio_key": key, "convenio_nome": key, "status": status, "records_count": 0, "erro": None}

def test_resumir_lote_todos_ok():
    lote = resumir_lote("p", [_c("a", "ok"), _c("b", "ok")], [{"convenio_key": "a"}])
    assert lote["status"] == "ok"
    assert lote["success_count"] == 2
    assert lote["error_count"] == 0
    assert lote["fora_janela_count"] == 0
    assert lote["records"] == [{"convenio_key": "a"}]

def test_resumir_lote_misto():
    lote = resumir_lote("p", [_c("a", "ok"), _c("b", "erro"), _c("c", "fora_janela")], [])
    assert lote["status"] == "partial_success"
    assert lote["success_count"] == 1
    assert lote["error_count"] == 1
    assert lote["fora_janela_count"] == 1
```

- [ ] **Step 2 — rodar, confirmar FAIL** (`ImportError: resumir_lote`)
`./env/Scripts/python.exe -m pytest tests/services/test_coleta_service_resumo.py -q`

- [ ] **Step 3 — implementar**
Em `app/services/coleta_service.py`, adicionar (perto de `_calcular_status_lote`):
```python
def resumir_lote(processadora_key: str, convenios: list[dict], records: list[dict]) -> dict:
    """Monta o dict de resultado do lote a partir dos convênios e records."""
    return {
        "processadora": processadora_key,
        "status": _calcular_status_lote(convenios),
        "total_convenios": len(convenios),
        "success_count": sum(1 for c in convenios if c["status"] == "ok"),
        "error_count": sum(1 for c in convenios if c["status"] not in ("ok", "fora_janela")),
        "fora_janela_count": sum(1 for c in convenios if c["status"] == "fora_janela"),
        "records": records,
        "convenios": convenios,
    }
```
E trocar o `return {...}` final de `executar_coleta_lote` por:
```python
    return resumir_lote(processadora_key, resultados_convenios, records_consolidados)
```
(Remover o bloco antigo do dict; o comportamento é idêntico.)

- [ ] **Step 4 — rodar, confirmar PASS** + a suíte de coleta_service:
`./env/Scripts/python.exe -m pytest tests/services/test_coleta_service_resumo.py tests/services/test_coleta_service_janela.py -q`

---

### Task 2: retry por-convênio + merge em orchestrator

**Files:** Modify `app/services/orchestrator.py`; Test `tests/services/test_orchestrator_retry.py` (acrescentar)

- [ ] **Step 1 — testes (falham nas asserções de `convenio_filter`)**
Acrescentar em `tests/services/test_orchestrator_retry.py` (reusa `_conv`, `_lote`, fixture `orch`):
```python
def test_recoleta_so_o_tecnico_que_falhou(orch):
    o, execucao_repo = orch
    inicial = _lote([_conv("a", "ok"), _conv("b", "erro", "Timeout 30000ms exceeded")])
    sub_b_ok = _lote([_conv("b", "ok")])
    mock = MagicMock(side_effect=[inicial, sub_b_ok])
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 2  # inicial + 1 re-coleta de b (a não é re-coletado)
    assert mock.call_args_list[1].kwargs.get("convenio_filter") == "b"
    execucao = execucao_repo.salvar.call_args[0][0]
    assert execucao.success_count == 2 and execucao.error_count == 0

def test_nao_recoleta_credencial_so_o_tecnico(orch):
    o, _ = orch
    inicial = _lote([_conv("a", "erro", "Autenticação falhou"), _conv("b", "erro", "Timeout 30000ms exceeded")])
    sub_b = _lote([_conv("b", "ok")])
    mock = MagicMock(side_effect=[inicial, sub_b])
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert [c.kwargs.get("convenio_filter") for c in mock.call_args_list] == [None, "b"]

def test_teto_por_convenio(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([_conv("b", "erro", "Timeout 30000ms exceeded")]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 3  # inicial + 2 re-coletas (teto), b nunca recupera
```

- [ ] **Step 2 — rodar, confirmar FAIL** (`test_recoleta_so_o_tecnico_que_falhou` falha: hoje a re-coleta usa o lote inteiro, convenio_filter=None)
`./env/Scripts/python.exe -m pytest tests/services/test_orchestrator_retry.py -q`

- [ ] **Step 3 — implementar**
Em `app/services/orchestrator.py`, substituir o corpo do `for tentativa ...` em `_coletar_lote_com_retry` e adicionar `_merge_convenio`. O método fica:
```python
    def _coletar_lote_com_retry(self, processadora: str, convenio_filter: str | None) -> dict:
        """Roda o lote e re-coleta POR-CONVÊNIO os que falham por erro técnico
        (teto _MAX_RETENTATIVAS_LOTE). Convênios ok / credencial / known_failure /
        fora_janela ficam intocados — não são re-coletados.
        """
        resultado_lote = executar_coleta_lote(processadora, convenio_filter=convenio_filter)
        for tentativa in range(1, _MAX_RETENTATIVAS_LOTE + 1):
            tecnicos = _erros_tecnicos_retentaveis(resultado_lote)
            if not tecnicos:
                break
            logger.warning(
                "Retentativa %d/%d do lote %s — re-coletando %d convênio(s): %s",
                tentativa, _MAX_RETENTATIVAS_LOTE, processadora, len(tecnicos),
                ", ".join(c.get("convenio_key", "?") for c in tecnicos),
            )
            for c in tecnicos:
                ck = c["convenio_key"]
                sub = executar_coleta_lote(processadora, convenio_filter=ck)
                resultado_lote = self._merge_convenio(processadora, resultado_lote, ck, sub)
        return resultado_lote

    @staticmethod
    def _merge_convenio(processadora: str, lote: dict, convenio_key: str, sub_lote: dict) -> dict:
        """Substitui o resultado de 1 convênio no lote pela re-coleta e recomputa o resumo."""
        from app.services.coleta_service import resumir_lote  # noqa: PLC0415 (import diferido, padrão do módulo)

        novo = next((c for c in sub_lote.get("convenios", []) if c.get("convenio_key") == convenio_key), None)
        if novo is None:
            return lote  # re-coleta não trouxe o convênio — mantém o anterior
        convenios = [novo if c.get("convenio_key") == convenio_key else c for c in lote.get("convenios", [])]
        records = [r for r in lote.get("records", []) if r.get("convenio_key") != convenio_key]
        records += [r for r in sub_lote.get("records", []) if r.get("convenio_key") == convenio_key]
        return resumir_lote(processadora, convenios, records)
```
(A docstring antiga do método e a "DÍVIDA DE V2" podem sair — a dívida foi paga.)

- [ ] **Step 4 — rodar testes do orchestrator** (`./env/Scripts/python.exe -m pytest tests/services/test_orchestrator_retry.py -q`) — todos passam.
- [ ] **Step 5 — SUÍTE COMPLETA** (`./env/Scripts/python.exe -m pytest -q`) — sem regressão (110 + novos).

## Verificação
`./env/Scripts/python.exe -m pytest -q` verde. Sem tocar portal (tudo mock).
