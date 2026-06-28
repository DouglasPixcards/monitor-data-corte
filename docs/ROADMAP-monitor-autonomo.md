# Roadmap — Monitor de Cortes autônomo, independente e principal em produção

> Tasks marcáveis (`- [ ]`). Ordem por dependência, não por valor isolado.
> Estado base (origem): 30/85 convênios, storage JSON, agendado por Task Scheduler do
> Windows numa máquina pessoal, e-mail diário, FastAPI.

## North star
Um serviço que sozinho coleta as datas de corte todo dia, em infra própria, se
auto-monitora e auto-alerta, serve os dados por painel + API confiáveis, e é a fonte
da verdade da operação — sem ninguém rodar nada local.

---

## Estado atual (2026-06-28)

**Todo o trabalho de CÓDIGO local (Trilhas A + dado + produto + observabilidade) está
feito e na `main` — 195 testes verdes, CI rodando a suíte + Postgres a cada push.** O que
resta está **bloqueado em terceiros** (VM dedicada, subdomínio via Higor, rotação do muana)
ou é cobertura/refino incremental.

**✅ Concluído:**
- **Trilha A:** retry por-convênio · erro tipado (`erro_categoria`) · detecção credencial/portal.
- **Fase 4 (dado) — completa:** validação de `data_corte` · flag de confiança (origem
  estimado/oficial **+** estável/instável) · histórico por convênio · reconciliação (salto).
- **Fase 5 (produto) — essencialmente completa:** painel React (board) · calendário · webhooks
  de mudança · auth (HTTP Basic).
- **Observabilidade:** métricas (taxa por processadora + falhas por convênio) · **dead-man's
  switch** (código) · CI com Postgres.
- **Backend:** **D3 = Postgres adotado** (endurecido + script de migração JSON→PG + CI).
- **Segurança:** histórico limpo + tags · `.gitignore` blindado (`secrets/`, `.env.*`).

**🔴 Bloqueado em terceiros / suas pendências:**
- **VM dedicada** (contratar) → destrava todo o deploy (Fase 1b + runtime/cron/logs da Fase 2).
- **Rotacionar a senha do muana** antes do go-live (inegociável).
- **Subdomínio `cortes.pixcard.io`** (pedir ao Higor).

**🟢 Ainda dá pra fazer local (incremental):** alerting com severidade + Slack · lint (ruff) no
CI · runbook `OPERACAO_V1` · framework de coletor padronizado · SafeConsig V2 · cobertura 30→85.

---

## Decisões-chave

- [x] **D1 — RESOLVIDO (2026-06-26):** servidor atual (1 CPU/1.6GB + bolão) **não suporta**
  Playwright → runtime/deploy adiado para **VM dedicada**. Coleta confirmada **sequencial**
  (`_exec_lock` no runner, 1 Chromium por vez). Sizing recomendado: 2 vCPU / 4GB / 25GB SSD.
- [ ] **D2 — Empacotamento: Docker vs systemd+venv.** Decidir no deploy. `docker-compose.yml`
  já pronto e validado no CI; systemd+venv é o padrão da casa (bolao) e mais leve. **Recomendo
  systemd+venv**; Docker só se a isolação das deps do Chromium virar dor.
- [x] **D3 — RESOLVIDO: Postgres.** Backend adotado e endurecido (paridade, fail-fast,
  `alembic check` no CI) + script de migração JSON→PG idempotente. SQLite descartado.

---

## Fase 0 — Segurança (CONCLUÍDA, exceto rotação deferida)
> ⚠️ A limpeza reduz exposição futura mas NÃO neutraliza o segredo já vazado — **regra dura:
> rotacionar a senha do muana ANTES de ir pra produção** (Fase 1b).

- [x] Commitar o trabalho consolidado (ConsigUp + specs + planos).
- [x] Backup espelho do repo antes de reescrever.
- [x] `git filter-repo` removendo o blob da credencial muana do histórico.
- [x] `.gitignore` blindado (`secrets/`, `.env.*`, mantém `.env.example`); `.env` nunca no histórico.
- [x] Force-push em `main` e `feat/registro-falha-coleta`.
- [x] Git tags anotadas na versão consolidada.
- [ ] *(follow-up)* Varredura profunda por **outros** segredos no histórico (gitleaks/`/cso`).

## Fase 2 — Autonomia & confiabilidade (Trilha A feita; runtime bloqueado na VM)
- [x] **D1** — investigação de memória / coleta sequencial confirmada.
- [x] **Retry por-convênio** (`687945e`) — não re-coleta o que já deu certo.
- [x] **Tipo de erro estruturado** (`b048e03`) — `erro_categoria` tipado + fallback heurístico.
- [x] **Detecção proativa de portal quebrado / credencial expirada** (`cb07221`) — alerta acionável.
- [x] **Dead-man's switch** (`56b9f54`) — ping de uptime ao fim da coleta (código). Falta só
  **criar o check externo** (healthchecks.io) e setar `HEALTHCHECK_URL` na VM.
- [ ] 🔴 **Runtime mínimo no servidor** (`/opt/monitor-cortes`, venv, systemd, `127.0.0.1:8001`) — VM.
- [ ] 🔴 **Scheduler de produção:** cron chamando o runner diário (respeitando a janela do ConsigUp) — VM.
- [ ] 🔴 Logs operáveis (journalctl/`cron.log`) — VM.

## Fase 4 — Qualidade do dado (CONCLUÍDA)
- [x] Normalização/validação robusta de `data_corte` (`8a8ab16`) — garbage vira `valor_invalido`.
- [x] **Flag de confiança por convênio** — origem estimado/oficial/manual (`e346bd5`) +
  estável/instável por frequência de mudança de dia (`fb99980`).
- [x] Histórico/auditoria de mudanças exposto (`16fe3f4` + painel `a0e8f9e`).
- [x] Reconciliação — salto grande de data sinalizado "conferir" (`5b3184b`).

## Fase 5 — Produto & interface (essencialmente CONCLUÍDA)
- [x] **Painel single-page live** — app React/Vite em `/painel` (board ao vivo de `/cortes/atuais`).
- [x] **Calendário de cortes** (`7c3d762`) — vista mensal, aba no painel.
- [x] **Webhooks** de mudança de data (`0ddda96`). *(API estável formal: OpenAPI auto do FastAPI;
  versionamento/contrato formal = follow-up se outro sistema consumir.)*
- [x] **Auth/controle de acesso** no painel (`78578f6`) — HTTP Basic opt-in, leitura + escrita.

## Fase 1b — Deploy polido (🔴 TODO BLOQUEADO na VM / Higor / muana)
- [ ] Subdomínio **`cortes.pixcard.io`** → pedir ao **Higor**.
- [ ] Nginx (proxy `127.0.0.1:8001`) + **Certbot SSL** (Cloudflare Full strict).
- [ ] `deploy/deploy.sh` (git pull → deps → build → restart).
- [ ] **Backup diário** dos dados (7 dias).
- [ ] `.env` na VM; **secrets gerados na VM**, nunca no git.
- [ ] **🔒 Rotacionar a senha do muana** — antes do go-live.
- [x] Decisão **D3** (Postgres) — aplicada; rodar a migração na VM no cutover.

## Fase 3 — Cobertura (incremental, local)
- [ ] **Framework de coletor padronizado** — auth + seletores em config — pra adicionar portal custar pouco.
- [x] **Migração de storage** (D3 / Postgres) — script pronto e validado.
- [ ] Integrar **ZETRASOFT + CIP** (precisa de acesso/credencial aos portais).
- [ ] Mapear/implementar os convênios restantes (**30 → ~85**).
- [ ] **SafeConsig V2:** adapter → `ApiCollector` genérico; competência vs data oficial.
- [ ] **Integrar ao registro central de convênios** (hoje `processadoras.json` isolado).

## Contínuo — observabilidade & governança
- [x] **Métricas** (`f9c1816`) — taxa de sucesso por processadora (tendência) + falhas por convênio.
- [x] Alerting por **e-mail** (digest com seções acionáveis). [ ] **Severidade + Slack/webhook** = follow-up.
- [x] **CI:** suíte (195 testes) + Postgres + `alembic check` a cada push. [ ] **lint (ruff)** = follow-up.
- [x] Runbook **`POSTGRES.md`**. [ ] Atualizar `OPERACAO_V1` + doc "como adicionar um portal".

---

## Caminho crítico (atualizado)
Código local (**Trilha A → Fase 4 → Fase 5 → observabilidade**) **✅ feito**.
Resta: **contratar a VM → Fase 2 runtime + Fase 1b deploy (com rotação do muana) → Fase 3
cobertura.** Itens locais soltos (alerting/severidade, lint, framework de coletor, runbook)
podem andar a qualquer momento, sem dependência.

> Regra de produção: **rotacionar o muana antes do go-live** (Fase 1b) — inegociável.
