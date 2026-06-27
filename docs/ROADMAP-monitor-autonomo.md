# Roadmap — Monitor de Cortes autônomo, independente e principal em produção

> Tasks marcáveis (`- [ ]`). Ordem por dependência, não por valor isolado.
> Estado base: 30/85 convênios, storage JSON, agendado por Task Scheduler do Windows
> numa máquina pessoal, e-mail diário, FastAPI. Já feito nesta fase: ConsigNet
> (reCAPTCHA), ConsigLog (validate_access + popup), retry opt-in + classificação de
> rede, janela do ConsigUp (não-commitado).

## North star
Um serviço que sozinho coleta as datas de corte todo dia, em infra própria, se
auto-monitora e auto-alerta, serve os dados por painel + API confiáveis, e é a fonte
da verdade da operação — sem ninguém rodar nada local.

---

## Decisões-chave (resolver cedo — moldam tudo)

- [ ] **D1 — Playwright em 1 CPU / 1.6GB RAM (maior risco técnico).** O servidor é
  pequeno e já roda o `bolao`. Headless Chromium para vários portais é pesado.
  **Tarefa de investigação (Fase 2):** medir o pico de memória de UMA coleta;
  confirmar coleta **estritamente sequencial** (1 scraper por vez); flags de baixa
  memória (`--single-process`, `--disable-dev-shm-usage`, headless shell); confiar no
  swap (5.3GB) com cautela; decidir se o scraping cabe nesse box ou precisa de worker
  separado / janela noturna fora do horário do bolao.
- [ ] **D2 — Empacotamento: Docker vs systemd+venv.** Padrão da casa = **systemd+venv**
  (o bolao). Você mencionou Docker. Trade-off: Docker encapsula as ~30 libs de sistema
  do Playwright (limpo), mas custa RAM/disco no box pequeno; systemd+venv casa com a ops
  e é mais leve, mas exige instalar as deps do Chromium no host. **Recomendo systemd+venv**
  (alinha com o bolao e economiza RAM); Docker só se a isolação das deps virar dor.
- [ ] **D3 — Storage: SQLite (padrão da casa, 1 worker) vs Postgres.** O monitor escreve
  durante coletas longas e o painel lê em paralelo. Avaliar se SQLite+1worker basta
  (como o bolao) ou se a concorrência coleta×painel pede Postgres. **Decidir antes da
  Fase 4/5.** (Já existe `app/storage/postgres_storage.py`.)

---

## Fase 0 — Limpeza de histórico + tag (segurança, AGORA)
> Rotação da senha do muana fica **deferida** (decisão sua); limpeza do histórico = agora.
> ⚠️ A limpeza reduz exposição futura mas NÃO neutraliza o segredo já vazado — **regra
> dura: rotacionar a senha do muana ANTES de ir pra produção** (fechado na Fase 1b).

- [ ] Decidir e **commitar o trabalho não-commitado de hoje** (feature ConsigUp + spec +
  plano + handoff) — para entrar na versão "consolidada".
- [ ] **Backup espelho do repo** (`git clone --mirror`) antes de reescrever.
- [ ] `git filter-repo` removendo o blob da credencial muana do `app/core/processadoras.json`
  em todo o histórico (introduzido em `f118f85`/`4fbebbb`).
- [ ] Auditar o histórico por **outros segredos** (não só o muana) — `/cso` / varredura.
- [ ] **Force-push** em `main` e `feat/registro-falha-coleta`; re-clonar onde houver cópia.
- [ ] **Criar git tag anotada** (ex.: `v1.0-consolidado`) na versão consolidada — o marco
  que você quer lembrar.
- [ ] Confirmar que `.gitignore` cobre `.env` e que nenhuma outra credencial está embutida
  na config (hoje já é `credential_env_key`).

## Fase 2 — Autonomia & confiabilidade (+ runtime mínimo)
> Aqui também sai da sua máquina para um runtime mínimo no servidor — porque autonomia só
> se prova rodando sozinha.

- [ ] **D1** — investigação de memória do Playwright no box (acima). É pré-requisito do resto.
- [ ] **Runtime mínimo no servidor:** `/opt/monitor-cortes`, venv, serviço systemd
  (porta interna 8001, `--host 127.0.0.1`), conforme o template do servidor. Sem painel
  polido ainda — só rodar a API + o job.
- [ ] **Scheduler de produção:** migrar do Task Scheduler do Windows para **cron** no
  servidor (padrão do bolao) chamando o runner diário; respeitar a janela do ConsigUp.
- [ ] **"Quem vigia o vigia":** dead-man's switch externo — cada rodada pinga um serviço de
  uptime (ex.: healthchecks.io); se a rodada faltar/atrasar, alerta **independente** do
  próprio sistema.
- [ ] **Retry por-convênio** (hoje é por-processadora — dívida V2): não re-coletar o que já
  deu certo.
- [ ] **Tipo de erro estruturado:** cada coletor devolve uma causa tipada; aposentar a
  heurística por string do `erro_classifier`.
- [ ] **Detecção proativa de portal quebrado / credencial expirada** → alerta acionável
  (generalizar o aprendizado de ConsigNet/ConsigLog).
- [ ] Logs operáveis (journalctl via systemd e/ou `cron.log`).

## Fase 4 — Qualidade do dado (fonte da verdade confiável)
- [ ] Normalização/validação robusta de `data_corte`.
- [ ] **Flag de confiança por convênio** (estável vs instável; **estimado vs oficial** —
  SafeConsig hoje é estimativa de competência).
- [ ] Histórico/auditoria de mudanças exposto e versionado (já há eventos).
- [ ] Reconciliação periódica (detectar valores improváveis).

## Fase 5 — Produto & interface (o que a operação usa)
- [ ] **Painel single-page live** — `dashboard_executivo.html` servido pela API: datas
  atuais, status por convênio, falhas, histórico.
- [ ] **Calendário de cortes** (`frontend-calendario`) integrado.
- [ ] **API estável** para outros sistemas + **webhooks** de mudança de data.
- [ ] **Auth/controle de acesso** no painel.

## Fase 1b — Deploy polido (produção real)
> O runtime mínimo já subiu na Fase 2; aqui é o acabamento de produção.

- [ ] Subdomínio **`cortes.pixcard.io`** → pedir ao **Higor** apontar para `45.32.222.236`.
- [ ] Config Nginx (template do servidor), proxy para `127.0.0.1:8001`.
- [ ] **Certbot SSL** (`certbot --nginx -d cortes.pixcard.io`) — Cloudflare **Full (strict)**.
- [ ] `deploy/deploy.sh` (git pull → deps → build → restart), no padrão do bolao.
- [ ] **Backup diário** dos dados (script no padrão do `bolao backup.sh`, 7 dias).
- [ ] `.env` em `/opt/monitor-cortes/backend/.env`; **secrets gerados na VM**, nunca no git.
- [ ] **🔒 Rotacionar a senha do muana** (fecha o item deferido da Fase 0) — antes do go-live.
- [ ] Aplicar a decisão **D3** (SQLite vs Postgres) conforme a carga real.

## Fase 3 — Cobertura (por último; enablers adiantados)
- [ ] *(adiantar na consolidação)* **Framework de coletor padronizado** — auth + seletores
  em config + base scraper — para adicionar portal custar pouco.
- [ ] *(adiantar na consolidação)* **Migração de storage** se a Fase 4/5 exigir (D3).
- [ ] Integrar **ZETRASOFT + CIP** (o 80/20 do que falta).
- [ ] Mapear/implementar os convênios restantes (**30 → ~85**).
- [ ] **SafeConsig V2:** sair do adapter temporário → `ApiCollector` genérico; resolver
  estimativa de competência vs data de corte oficial.
- [ ] **Integrar ao registro central de convênios** (hoje `processadoras.json` isolado).

## Contínuo — observabilidade & governança
- [ ] Métricas (taxa de sucesso por convênio/processadora, tendências).
- [ ] Alerting acionável (e-mail + talvez Slack/webhook, com severidade).
- [ ] **CI:** rodar a suíte (110+ testes) + lint a cada PR.
- [ ] Runbook atualizado (`OPERACAO_V1`) + doc "como adicionar um portal".

---

## Caminho crítico (resumo)
**0 (limpeza + tag) → 2 (autonomia + runtime mínimo, gate em D1) → 4 (dado) → 5 (produto)
→ 1b (deploy polido + rotação do muana) → 3 (cobertura).**
Decisões D1/D2/D3 resolvidas no começo da Fase 2.

> Regra de produção: **rotacionar o muana antes do go-live** (Fase 1b) — inegociável.
