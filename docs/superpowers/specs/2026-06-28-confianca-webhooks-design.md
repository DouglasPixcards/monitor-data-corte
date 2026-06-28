# Spec — Confiança (fecha Fase 4) + Webhooks (inicia Fase 5)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (run autônomo)

## A — Flag de confiança por convênio (fecha a Fase 4)
**Problema:** falta a outra metade da flag (origem já existe) — quão **estável** é a data de
corte de um convênio. Um convênio que muda toda hora merece menos confiança.

**Design:**
- `app/services/confianca.py`: `classificar_confianca(mudancas: int) -> str` (puro) —
  `0 → "estavel"`, `1–2 → "media"`, `≥3 → "instavel"` (mudanças = nº de `DATA_CORTE_ALTERADA`
  na janela de 90 dias).
- `api/main.py:_montar_dados_convenios`: por processadora, carrega `evento_repo.listar(proc, dias=90)`
  UMA vez e conta só as mudanças em que o **dia do mês** muda (`mudou_dia_corte`) por `convenio_key`
  — avanço normal de mês (mesmo dia) e competência `MM/YYYY` **não** contam, senão um corte estável
  que só roda de mês viraria "instável". Seta `"confianca"` em cada linha (~1 query/processadora).
  `/cortes/atuais` expõe `confianca`.
- **Painel:** badge "instável" (vermelho) quando `confianca == "instavel"`.

**Testes:** `classificar_confianca` (0/1/3); `/cortes/atuais` expõe `confianca` (mock de eventos).

## B — Webhooks de mudança de data (inicia a Fase 5)
**Problema:** quando uma data de corte muda, só o e-mail avisa — outros sistemas ficam de fora.

**Design:**
- `settings.WEBHOOK_URLS`: lista (CSV) de URLs, do env (como `notification_DESTINATARIOS`).
- `app/services/notification/webhook.py`: `disparar_mudancas(eventos, urls=None)` — para cada
  `DATA_CORTE_ALTERADA`, faz `POST` JSON `{convenio_key, processadora, folha, mes_atual,
  data_corte_anterior, data_corte_nova, detectado_em}` a cada URL. **Falha de POST é engolida**
  (não derruba a coleta); sem URLs = no-op.
- `orchestrator.coletar`: após `evento_repo.salvar_lote`, chama `disparar_mudancas(eventos)`.

**Testes:** `disparar_mudancas` posta o payload certo nas URLs (mock `requests.post`); sem URL =
no-op; eventos não-DATA ignorados; erro de POST não propaga.

## Fora de escopo (próximos da Fase 5)
- Calendário de cortes · auth no painel · API estável formal — itens seguintes.
