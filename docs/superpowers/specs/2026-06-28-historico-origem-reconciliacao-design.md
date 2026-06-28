# Spec — Histórico por convênio + origem + reconciliação (Fase 4)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado

Três features encadeadas: **C (histórico)** é a fundação; **A (origem)** é independente;
**B (reconciliação)** usa o histórico + a validação de `data_corte` (já feita).

## Decisões (aprovadas)
- Histórico: **fonte = eventos de mudança** (`DATA_CORTE_ALTERADA` + `REGISTRO_NOVO`).
- Histórico: **endpoint na API + vista no painel** (React).
- Origem: **só `origem`** (estimado/oficial/manual) agora; confiança fica pra reconciliação/depois.
- Reconciliação: **salto grande vs o último valor** conhecido.

## Execução
Backends primeiro (limpos), frontend consolidado por último (o painel hoje está não-commitado).

---

## C — Histórico por convênio
**Backend:**
- `EventoRepository.listar(processadora, dias=30, convenio_key=None)` — novo filtro opcional
  `convenio_key` (compatível: default None = comportamento atual). Em **ABC + file + postgres**.
  - file: filtra as linhas após carregar; postgres: `AND convenio_key = ?` (índice em `convenio_key`).
- Endpoint `GET /convenios/{key}/historico?dias=` — resolve a key → (processadora, convenio_key),
  chama `listar(processadora, dias, convenio_key)`, filtra aos tipos de data
  (`DATA_CORTE_ALTERADA`, `REGISTRO_NOVO`) e devolve a timeline
  `[{detectado_em, tipo, data_corte_anterior, data_corte_nova, folha, mes_atual}]`. `dias` default amplo.

**Frontend (passo final):** clicar num convênio no painel → vista/modal de histórico que busca
`/convenios/{key}/historico` e renderiza a timeline.

**Testes:** file/postgres `listar` com `convenio_key` (filtra certo + default None inalterado);
endpoint devolve a timeline do convênio.

---

## A — origem (estimado vs oficial vs manual)
**Schema (mudança):** `DadoCorte.origem: str | None` (valores `"scraper"` | `"api_estimativa"` |
`"manual"`). Em `models.py`, `sql_models.py` (+ migration `0003`), e o round-trip do file_storage.
- `coleta_service`: ao montar o `DadoCorte`, seta `origem` por tipo de coletor
  (`integration_type=="api"` → `api_estimativa`; scraper → `scraper`). O endpoint manual → `manual`.
- **Substitui o sentinela frágil** `folha="virada_competencia"` como sinal de "estimativa"
  (mantém o folha como está, mas a origem passa a ser a fonte da verdade da linguagem).
- **Digest/painel:** badge "estimativa" quando `origem == "api_estimativa"`.

**Testes:** round-trip de `origem` (file + postgres); coleta_service seta a origem certa; digest mostra o badge.

---

## B — Reconciliação (salto grande)
- `reconciliar_data_corte(anterior, atual, ...)` (puro): se ambos são `DD/MM/YYYY` válidos e o
  **salto em dias** entre eles excede um teto (ex.: `_MAX_SALTO_DIAS`, default ~25), é improvável.
- No **comparador**, quando emite `DATA_CORTE_ALTERADA` com salto grande → também emite um sinal
  tipado `salto_suspeito` (categoria nova, acionável "conferir") — não bloqueia a mudança, só alerta.
- **Testes:** salto pequeno (normal) vs grande (suspeito); MM/YYYY / None não disparam.

## Fora de escopo
- Confiança (estável vs oscilante) como flag separada — adiada (origem + reconciliação cobrem o essencial).
- Divergência estatística do padrão histórico — versão mais sofisticada, depois.
