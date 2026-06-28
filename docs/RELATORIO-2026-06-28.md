# Relatório de desenvolvimento — Monitor de Datas de Corte

Data: 2026-06-28 · Branch: `feat/registro-falha-coleta` (= `main`) · Tip: `a0e8f9e`

Documento do que foi implementado na sessão, fase a fase. **15 commits**, todos com
spec → implementação (TDD) → revisão (opus, adversarial) → commit. Suíte ao fim:
**177 testes com Postgres** (155 passados + 22 que pulam localmente sem banco).

---

## Visão geral

| Fase | Entrega | Commits |
|---|---|---|
| **Trilha A** — inteligência de monitoramento | retry por-convênio · erro tipado · detecção credencial/portal | `687945e` `b048e03` `cb07221` |
| **CI + Segurança** | suíte a cada push · blindagem de segredos | `f239f7f` `570d1df` |
| **Postgres (D3)** | backend endurecido · CI valida · script de migração · fix httpx | `811fec5` `32f4c81` `efb43b4` `8639591` |
| **Fase 4** — qualidade do dado | validação · histórico · origem · reconciliação · painel | `8a8ab16` `16fe3f4` `e346bd5` `5b3184b` `528e67a` `a0e8f9e` |

---

## Fase: Trilha A — inteligência de monitoramento

Tornar o monitor mais inteligente ao lidar com falhas.

### 1. Retry por-convênio — `687945e`
**Problema:** o retry agendado re-rodava o **lote inteiro** (re-coletando convênios que já
deram certo e os de credencial, que nunca recuperam) — a "dívida V2".
**Entrega:** re-coleta só os convênios com **erro técnico** que ainda falham (um a um, via
`convenio_filter`), fundindo o resultado no lote. `ok` / credencial / `known_failure` /
`fora_janela` ficam intocados. `resumir_lote` extraído (DRY).

### 2. Erro tipado (`erro_categoria`) — `b048e03`
**Problema:** a causa do erro era derivada por **heurística de string** (frágil — "senha
expirada" e "senha inválida" caíam no mesmo balde).
**Entrega:** o coletor pode **declarar a categoria** (`CollectionError(categoria=...)`),
propagada pelo `base_scraper` no resultado; comparador e retry **preferem** o tipado e caem
no `classificar_erro(string)` como fallback. SafeConsig deriva a categoria do tipo da exceção;
`CredentialNotFoundError → auth_falhou`. Incremental e compatível.

### 3. Detecção (credencial expirada + portal quebrado) — `cb07221`
**Entrega:** categoria nova **`credencial_expirada`** (excluída do retry — determinística;
destaque **acionável** no topo do e-mail "renovar a senha", `[Ação]` mesmo se persistente).
ConsigLog vira produtor tipado: `validate_access` levanta `credencial_expirada`/`auth_falhou`;
`collect` levanta `portal_mudou`. Demais scrapers adotam o padrão incrementalmente (fallback cobre).

---

## Fase: CI + Segurança

### CI — `f239f7f`
GitHub Actions roda a suíte (pytest) em **todo push e PR** — rede de segurança contra regressão
antes de chegar na coleta diária.

### Blindagem de segredos — `570d1df`
`.gitignore` ganha `secrets/` + `.env.*` (mantendo `.env.example` via negação) — fecha o risco de
commit acidental de segredos (lição do incidente muana). Verificado que `.env` **nunca** esteve no
histórico.

---

## Fase: Adoção do Postgres (decisão D3)

O mapa revelou que o **backend Postgres já estava construído** (repos, `sql_models`, `db`,
migrations Alembic, docker-compose). O trabalho foi **validar + endurecer**, não buildar.

### Hardening — `811fec5`
- `buscar_por_execucao`: `ORDER BY` determinístico (evita diffs instáveis).
- `db.assert_ready()`: **fail-fast no startup** (runner + API via SchedulerService) quando
  `STORAGE_BACKEND=postgres` — DB acessível + schema na **head** do Alembic, em vez de falhar
  lazy na 1ª query.
- `alembic.ini`: `path_separator=os`.

### CI valida o Postgres + runbook — `32f4c81`
Serviço **Postgres 16** no CI: `alembic upgrade head` (migrations do zero) + `alembic check`
(guarda **real** de drift modelo↔migration) + a suíte com `TEST_DATABASE_URL` — as parity tests
do Postgres passam a **rodar de verdade** a cada push. + `docs/POSTGRES.md` (runbook bare-metal).

### Script de migração JSON → Postgres — `efb43b4`
`scripts/migrate_json_to_postgres.py`: backfill **idempotente** (`ON CONFLICT DO NOTHING` na PK),
**chunked** (lotes de 1000, sob o teto de 65535 params), `--dry-run`, tolerante a malformados.
Validado e2e contra o corpus real: **543 linhas, 341 dados_corte preservadas**, 2ª rodada = 0.

### Fix de CI — `8639591`
A coleta de testes quebrava no CI: `requirements.txt` não trazia `httpx` (exigido pelo
`TestClient`). Pinado o stack web (`fastapi==0.136.1`, `starlette==1.0.0`, `httpx==0.28.1`).

> **2 bugs sérios pegos antes de produção nesta fase:**
> 1. Uma `UNIQUE(execucao_id, convenio_key)` que eu havia adicionado **descartaria ~55% das
>    linhas** na migração — o dado real mostra que um convênio tem **múltiplas folhas/órgãos**
>    por execução (pego validando contra `data/` real; constraint removida).
> 2. O `INSERT` único do corpus inteiro **estouraria o limite de parâmetros** do Postgres num
>    corpus grande (pego na revisão adversarial; corrigido com chunking).

---

## Fase 4 — Qualidade do dado (fonte da verdade confiável)

### Validação de `data_corte` — `8a8ab16`
`validar_data_corte()` aceita `DD/MM/YYYY` (data real, ano da coleta ±1) ou `MM/YYYY`
(competência/estimativa); o resto é garbage. O comparador, **antes** de emitir
`DATA_CORTE_ALTERADA`, valida o valor — um scrape quebrado que retorna `"ver tabela"` vira
sinal tipado **`valor_invalido`** (seção "⚠️ conferir" no e-mail), **não** um falso "data alterada".

### Histórico por convênio — `16fe3f4` (backend) + `a0e8f9e` (painel)
- `EventoRepository.listar` ganha filtro opcional **`convenio_key`** (ABC + file + postgres).
- Endpoint `GET /convenios/{key}/historico` → a **timeline** de `data_corte` do convênio
  (mudanças `DATA_CORTE_ALTERADA` + 1º `REGISTRO_NOVO`).
- Painel React: clicar no convênio abre um **modal com a linha do tempo**.

### Origem (estimado vs oficial vs manual) — `e346bd5` + `a0e8f9e`
- `DadoCorte.origem` (`scraper` | `api_estimativa` | `manual`) — setado na coleta pelo
  `integration_type`, persistido em file + postgres (**migration 0003**). Substitui o sentinela
  frágil `folha="virada_competencia"`.
- `/cortes/atuais` expõe `origem`; o painel mostra um **badge "estimativa"**.

### Reconciliação (salto grande) — `5b3184b`
`salto_data_corte_suspeito()`: salto em dias entre duas datas `DD/MM/YYYY` acima de
**45 dias** é improvável. Ao emitir `DATA_CORTE_ALTERADA` com salto grande, o comparador
também emite **`salto_suspeito`** (seção "📈 conferir") — não bloqueia a mudança, só alerta.

### Consolidação do painel — `528e67a`
Commitado o WIP do painel: app **React/Vite** (`frontend/`, board ao vivo de `/cortes/atuais`)
montado em `/painel`; API e runner passam a usar a **factory** (`build_orchestrator`/
`build_repositories`) — backend-agnostic (file/postgres). Docker/deploy ficaram para a fase da VM.

---

## Estado do repositório

- **Branch `main` e `feat/registro-falha-coleta`** sincronizadas em `a0e8f9e` (origin = local).
- **Testes:** 177 com Postgres (CI) · 155 + 22 skip localmente sem banco.
- **Migrations Alembic:** `0001_inicial` → `0002_evento_falha_campos` → `0003_dados_corte_origem`.
- **CI verde** (suíte + Postgres + `alembic check` a cada push).
- **Frontend** builda limpo (`vite build`).

## Decisões de design registradas
- Erro tipado: categoria explícita + `classificar_erro` como fallback; migração **incremental**.
- Postgres: sem UNIQUE composto em `dados_corte` (multi-folha real) — só a PK `id`.
- Origem: campo no `DadoCorte`; o badge no painel é a apresentação.
- Reconciliação: salto > 45 dias = "conferir" (teto tunável, travado por teste de borda).

## Pendências (suas / próximas fases)
- **VM dedicada** → destrava o deploy (Trilha B); o Docker/compose já está pronto no working tree.
- **Rotacionar a senha muana** antes do go-live (inegociável).
- **Subdomínio** `cortes.pixcard.io` (pedir ao Higor) quando for pra deploy.
- **Cutover do Postgres** + rodar a migração na VM (script pronto e validado).
- Working tree ainda tem **Docker/deploy + docs** não-commitados (de propósito — fase da VM).
- Migração incremental dos demais scrapers pro erro tipado (fallback cobre até lá).
