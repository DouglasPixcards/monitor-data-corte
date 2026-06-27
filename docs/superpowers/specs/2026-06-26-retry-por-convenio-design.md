# Spec — Retry por-convênio

Data: 2026-06-26 · Branch: feat/registro-falha-coleta · Status: design aprovado

## Contexto

`ColetaOrchestrator._coletar_lote_com_retry` re-roda `executar_coleta_lote(processadora)`
— o **lote inteiro** — até `_MAX_RETENTATIVAS_LOTE` (2) vezes quando há erro técnico
(`_erros_tecnicos_retentaveis`). Isso tem duas perdas (a dívida V2 documentada):

- re-coleta convênios que **já deram certo** (cada coleta é um Playwright caro/lento);
- re-roda convênios de **credencial** (`auth_falhou`), que são determinísticos e nunca
  recuperam — desperdício e re-uso desnecessário de credencial.

## Objetivo

Re-coletar **somente os convênios técnicos que ainda estão falhando**, um a um, e
**fundir** o resultado de cada um de volta no lote. Convênios `ok`, de credencial,
`known_failure` e `fora_janela` ficam intocados.

## Design

### Fluxo (`orchestrator._coletar_lote_com_retry`)
1. Roda o lote completo uma vez: `executar_coleta_lote(processadora, convenio_filter=...)`.
2. Até `_MAX_RETENTATIVAS_LOTE` rodadas: calcula `_erros_tecnicos_retentaveis(lote)`
   (**definição inalterada**). Se vazio, para. Senão, para **cada** convênio técnico-falhando,
   re-coleta só ele via `executar_coleta_lote(processadora, convenio_filter=ck)` e funde no lote.
3. Devolve o lote fundido.

Efeito: convênio `ok` na rodada 1 não é re-coletado; credencial/known/fora_janela ficam
como estão; cada técnico re-tenta até 2×.

### Merge (`orchestrator._merge_convenio`)
Substitui o resultado de 1 convênio no lote e recomputa o resumo:
- troca a entrada do convênio em `lote["convenios"]` pela nova (do sub-lote);
- troca os `records` desse convênio (remove os antigos, adiciona os novos);
- recomputa `status` + contagens via `resumir_lote` (ver abaixo).

`resumir_lote` é importado de `coleta_service` por **import diferido** dentro do método,
no mesmo padrão do wrapper `executar_coleta_lote` já existente no `orchestrator.py` (evita
puxar a cadeia Playwright no import do módulo / nos testes).

### Refactor DRY (`coleta_service.resumir_lote`)
Extrair do final de `executar_coleta_lote` um helper público:

```python
def resumir_lote(processadora_key: str, convenios: list[dict], records: list[dict]) -> dict:
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

`executar_coleta_lote` passa a terminar com
`return resumir_lote(processadora_key, resultados_convenios, records_consolidados)`.
`_calcular_status_lote` não muda.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `app/services/coleta_service.py` | extrair `resumir_lote`; `executar_coleta_lote` usa ele (comportamento idêntico) |
| `app/services/orchestrator.py` | reescrever `_coletar_lote_com_retry` (re-coleta por-convênio + merge); novo `_merge_convenio`; log "re-coletando N convênio(s)" |

## Testes (TDD, mock)
- `resumir_lote`: contagens/status corretos (ok / técnico / fora_janela / misto).
- Retry recupera só o técnico: lote inicial `[A ok, B técnico]`, re-coleta de B retorna ok →
  **2 chamadas** (inicial + `convenio_filter="B"`); A **não** re-coletado; lote final A ok + B ok.
- Não re-coleta credencial: `[A credencial, B técnico]` → re-coleta só B (`convenio_filter="B"`).
- Teto: B nunca recupera → re-coletado até 2× e para (3 chamadas).
- Os testes existentes de `test_orchestrator_retry.py` seguem passando (call_count compatível
  para lotes de 1 convênio).

## Decisões (mantidas)
- **Teto = 2** rodadas (cada convênio até 2 retentativas).
- **Escopo: só o caminho agendado** (`retentar_tecnico=True`).
- **Take-last por convênio:** só re-coletamos os que falham; o que recupera vira ok, o que
  segue falhando fica com o último resultado.

## Fora de escopo
- Tipo de erro estruturado e detecção de portal/credencial (próximos itens da Trilha A).
- `coleta_service.py` é arquivo crítico (OPERACAO_V1): a mudança é uma extração de helper
  sem alterar o comportamento de `executar_coleta_lote`.
