# Postgres — backend de storage

O monitor suporta dois backends de storage, escolhidos por env var:
`STORAGE_BACKEND=file` (JSON em disco, default zero-config) ou `STORAGE_BACKEND=postgres`.
Em produção o alvo é **Postgres**. Este doc é o runbook do Postgres **fora do Docker**
(bare-metal na VM); no Docker o `docker-compose.yml` já cuida de tudo (serviço `migrate`).

## 1. Subir o banco (uma vez, na VM)
```sql
CREATE USER monitor WITH PASSWORD '<senha-gerada-na-vm>';
CREATE DATABASE monitor OWNER monitor;
```
> Nunca commitar a senha. Gere na VM e coloque só no `.env` de lá (já gitignored).

## 2. Configurar o ambiente
No `.env` da VM (`/opt/monitor-cortes/.env`, fora do git):
```
STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg://monitor:<senha>@localhost:5432/monitor
STORAGE_PATH=data        # AINDA necessário: o runner grava o run-summary em data/runs/
```
O dialeto é `postgresql+psycopg` (psycopg3, já no `requirements.txt`).

## 3. Aplicar o schema (migrations)
```bash
python -m alembic upgrade head
```
Cria/atualiza as 3 tabelas (`execucoes`, `dados_corte`, `eventos`) até a revisão HEAD.
**Sempre rode isto após um deploy que tenha novas migrations** — o app NÃO cria tabelas
sozinho (não há `create_all` em produção).

## 4. Fail-fast no startup
Com `STORAGE_BACKEND=postgres`, o **runner diário** e a **API** (via `SchedulerService`, no
lifespan) chamam `db.assert_ready()` no início: verifica que o `DATABASE_URL` está setado, o
banco responde, e o schema está na **head** do Alembic. Se algo faltar, falha com mensagem
clara (ex.: "rode `alembic upgrade head`") em vez de quebrar silenciosamente na 1ª query —
protege a coleta agendada (nos dois caminhos).

## 5. Migrar o histórico JSON → Postgres (uma vez, no cutover)
Para preservar o histórico que hoje está em `data/*.json`:
```bash
# 1) ensaio: conta o que migraria, sem gravar nada
python scripts/migrate_json_to_postgres.py --source data --dry-run
# 2) pra valer (idempotente — pode re-rodar com segurança)
python scripts/migrate_json_to_postgres.py --source data
```
O script é **idempotente** (`ON CONFLICT DO NOTHING` na PK `id`): re-rodar não duplica. Eventos
antigos sem `tipo` recebem `""` (mesma tolerância do file storage). Use o corpus autoritativo
(`data/`, apontado por `STORAGE_PATH`) — **não** o `app/api/data/` (amostra/stale). Os inserts
são chunked (lotes de 1000) p/ não estourar o teto de parâmetros do Postgres num corpus grande.
O `--dry-run` é um **teto otimista**: não consulta o DB, então numa re-execução superestima o
que de fato seria inserido (o número real só sai na execução de verdade).

## 6. Validação no CI
O `.github/workflows/ci.yml` sobe um Postgres 16 de serviço, roda `alembic upgrade head`
(migrations sobem do zero), `alembic check` (**guarda real de drift** modelo↔migration — falha
se sql_models.py tiver coluna sem migration) e a suíte completa com `TEST_DATABASE_URL` — então
as parity tests do Postgres **rodam de verdade** a cada push (e não ficam puladas como antes).

## Notas
- Datas são guardadas como **texto ISO-8601** (não `timestamptz`), de propósito: strings ISO
  ordenam lexicograficamente = cronologicamente, igual ao file storage. Garanta que todo
  timestamp seja ISO uniforme (zero-pad + offset fixo).
- `dados_corte` tem só a PK `id` como uniqueness — um convênio pode ter várias folhas/órgãos
  por execução, então não há chave composta única (seria perda de dados).
- Testes do Postgres pulam automaticamente sem `TEST_DATABASE_URL`/`DATABASE_URL` (rodam no CI
  e localmente com um container: `docker run -d -e POSTGRES_USER=monitor -e POSTGRES_PASSWORD=monitor -e POSTGRES_DB=monitor -p 5433:5432 postgres:16`).
