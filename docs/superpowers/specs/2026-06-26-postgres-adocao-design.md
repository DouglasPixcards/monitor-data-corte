# Spec — Adoção do Postgres (D3 resolvido)

Data: 2026-06-26 · Branch: feat/registro-falha-coleta · Status: design aprovado

## Realidade (o mapa revelou)
O backend Postgres **já está construído**: `repository.py` (3 ABCs), `postgres_storage.py`
(8 métodos, paridade explícita com o JSON), `db.py` (engine/session lazy), `sql_models.py`
(ORM, `JSONB` → Postgres-only), e migrations Alembic `0001_inicial` + `0002_evento_falha_campos`.
A seleção é por `STORAGE_BACKEND` (default `file`); o `docker-compose.yml` **já roda Postgres**
(serviço `migrate` faz `alembic upgrade head`; runner/api dependem dele). As **10 parity tests**
do Postgres existem mas são exatamente os **10 "skipped"** (sem Postgres vivo) — e o **CI não
roda nenhuma delas nem exercita as migrations**.

Logo, "adotar Postgres" = **validar + endurecer** o que já existe e preparar a **migração de dados**.

## Decisões (aprovadas)
- **D3 = Postgres.**
- **Histórico:** migrar o JSON existente pro Postgres (backfill, com dry-run).
- **Escopo desta rodada: completo** (validar + endurecer). Cutover real em produção espera a VM.

## Workstreams

### WS1 — CI valida o Postgres (o destravamento)
- `.github/workflows/ci.yml` ganha um **serviço Postgres** (`postgres:16`, healthcheck) + `TEST_DATABASE_URL`
  apontando pra ele → as **10 parity tests rodam** (a fixture usa `TEST_DATABASE_URL`/`DATABASE_URL`).
- Passo `alembic upgrade head` contra o Postgres do CI → **migrations exercitadas do zero** (hoje os
  testes usam `create_all`, então as migrations nunca rodam no CI).
- Passo `alembic check` → **guarda real de drift** modelo↔migration (falha se `sql_models.py` tiver
  coluna sem migration correspondente). `upgrade head` sozinho NÃO compara modelos vs migrations.
- Resultado: CI passa a rodar ~137 (127 + 10 PG); local segue 127 + 10 skip (sem PG).

### WS2 — Hardening (fechar os gaps reais do mapa)
- **Paridade:** `PostgresDadosCorteRepository.buscar_por_execucao` sem `ORDER BY` → ordem
  não-determinística. Adicionar `ORDER BY` determinístico (ex.: `convenio_key, id`).
- **Integridade:** validado contra o corpus real (`data/`) — um convênio tem MÚLTIPLAS
  folhas/órgãos por execução, e nem `(execucao_id, convenio_key, folha)` é único; só o `id` (PK).
  Logo NÃO há UNIQUE composto (seria perda de ~55% das linhas na migração); o guard de re-coleta
  é por `execucao_id` (fail-fast na aplicação, já existente). [Constraint inicial descartada após
  o achado no dado real.]
- **Fail-fast no startup:** com `backend=postgres`, hoje falha **lazy** (DATABASE_URL ausente /
  schema não-migrado só estoura na 1ª query). Adicionar `db.assert_ready()` (checa conexão +
  `alembic_version == head`) chamado no startup do runner diário e da API (via `SchedulerService`,
  chamado no lifespan) **quando** backend=postgres — erro claro, não query quebrada lá na frente.
- **Docs/config:** documentar standup bare-metal (CREATE DATABASE/USER, `DATABASE_URL`,
  `STORAGE_BACKEND=postgres`, `alembic upgrade head`); alinhar `.env.example`. Nota: `STORAGE_PATH`
  segue necessário (o runner escreve o run-summary JSON em `data/runs/` mesmo no Postgres).

### WS3 — Script de migração JSON → Postgres (backfill)
- `scripts/migrate_json_to_postgres.py`: lê o corpus **autoritativo** (`settings.STORAGE_PATH` = `data/`,
  **não** o `app/api/data/` que é amostra/stale), carrega Execucao/DadoCorte/Evento e insere no Postgres.
- Trata: **dedup de eventos** (PK `id` colide → pula); **eventos antigos sem `tipo`** (coluna NOT NULL →
  backfill default ou pula com aviso); **idempotência** (re-rodável); **`--dry-run`** (conta sem gravar);
  resumo claro do que migrou/pulou.
- Testes contra o Postgres (corpus JSON de amostra → asserts no PG).

### WS4 — Validação
- TDD local com um **Postgres descartável** (container Docker) — roda as 10 parity tests + os novos
  testes contra PG real. O CI espelha (WS1).

## Fora de escopo
- **Cutover real em produção** (apontar o sistema vivo pro Postgres) — espera a VM dedicada.
- **Flag `origem`/`confiança`** (Fase 4 #2) — feature seguinte, construída sobre o Postgres.

## Riscos / notas
- **Datas como string ISO:** ordenação e o filtro de janela de eventos dependem de ISO uniforme
  (mesmo formato/timezone). Garantir que `now_iso()` é uniforme (zero-pad, offset fixo).
- Dois corpora JSON existem (`data/` ativo vs `app/api/data/` amostra) — o backfill usa só o autoritativo.
- `psycopg[binary]` + dialeto `postgresql+psycopg` precisam instalar no CI (têm wheel Linux).
