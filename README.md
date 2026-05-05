# Monitor de Datas de Corte

Serviço de monitoramento automático de datas de corte de convênios consignados. Acessa os portais das processadoras via automação de browser (Playwright), detecta mudanças nas datas em relação à coleta anterior e envia alertas por e-mail.

---

## Sumário

- [Como funciona](#como-funciona)
- [Processadoras suportadas](#processadoras-suportadas)
- [Arquitetura](#arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Configurando convênios](#configurando-convênios)
- [Subindo a API](#subindo-a-api)
- [Endpoints](#endpoints)
- [Agendamento automático](#agendamento-automático)
- [Testes](#testes)
- [Storage — onde os dados ficam](#storage--onde-os-dados-ficam)
- [Testando SMTP manualmente](#testando-smtp-manualmente)

---

## Como funciona

```
Scheduler (APScheduler)
        │
        ▼
ColetaOrchestrator
        │
        ├── Carrega dados anteriores (FileStorage)
        │
        ├── Executa scrapers por convênio (Playwright)
        │
        ├── Salva execução + dados coletados (FileStorage)
        │
        ├── Compara com dados anteriores (ComparadorService)
        │        └── Detecta: DATA_CORTE_ALTERADA / REGISTRO_NOVO / REGISTRO_NAO_ENCONTRADO
        │
        ├── Persiste eventos detectados (FileStorage)
        │
        └── Envia e-mail digest se houver mudanças (SMTP)
```

A cada execução — seja agendada ou via API — o sistema:

1. Busca a última execução bem-sucedida da processadora
2. Roda os scrapers para cada convênio configurado
3. Persiste o resultado (execução + dados coletados)
4. Compara os dados novos com os anteriores
5. Persiste os eventos gerados (mudanças, novos registros, registros sumidos)
6. Envia e-mail digest caso alguma data de corte tenha sido alterada

---

## Processadoras suportadas

| Processadora | Autenticação | Status |
|---|---|---|
| **ConsigFácil** | Certificado digital (Chrome + perfil do usuário) | Funcionando |
| **ConsigUp** | Login e senha por convênio | Funcionando |
| **SafeConsig** | — | Em desenvolvimento |

---

## Arquitetura

```
app/
├── api/            # FastAPI — endpoints HTTP
├── auth/           # Estratégias de autenticação (certificado, login/senha)
├── core/           # Modelos, enums, settings, loader de configuração
├── scrapers/       # Scrapers por processadora (ConsigFácil, ConsigUp, SafeConsig)
├── services/       # Orquestrador, comparador, scheduler, notificação
└── storage/        # Interfaces de repositório + implementação em arquivo
```

### Camadas

- **`core/`** — domínio puro: modelos de dados (`Execucao`, `DadoCorte`, `Evento`), enums (`EventoTipo`, `CollectionStatus`, `AuthType`), configurações via `.env`
- **`scrapers/`** — automação de browser. Cada processadora tem seu próprio scraper herdando de `BaseScraper`. A autenticação é injetada como estratégia (`CertificateAuthStrategy`, `LoginPasswordAuthStrategy`)
- **`services/`** — lógica de negócio: orquestrador coordena o fluxo completo, comparador detecta mudanças, scheduler agenda execuções, notification monta e envia e-mails
- **`storage/`** — persistência. Interface abstrata em `repository.py`, implementação em arquivo JSON/JSONL em `file_storage.py`. Trocar para banco de dados no futuro requer apenas uma nova implementação da interface
- **`api/`** — FastAPI expõe os serviços via HTTP

---

## Estrutura do projeto

```
monitor-data-corte/
├── app/
│   ├── api/
│   │   └── main.py                  # FastAPI app, endpoints, lifespan
│   ├── auth/
│   │   ├── base_auth_strategy.py    # Interface de autenticação
│   │   ├── certificate_auth.py      # Autenticação por certificado digital
│   │   └── user_pass_auth.py        # Autenticação por login/senha
│   ├── core/
│   │   ├── enums.py                 # AuthType, CollectionStatus, EventoTipo
│   │   ├── exceptions.py            # Exceções de domínio
│   │   ├── loader.py                # Carrega processadoras.json
│   │   ├── models.py                # Execucao, DadoCorte, Evento (dataclasses)
│   │   ├── processadoras.json       # Configuração de processadoras e convênios
│   │   └── settings.py              # Configurações via variáveis de ambiente
│   ├── scrapers/
│   │   ├── base_scraper.py          # BaseScraper — ciclo start/authenticate/collect/stop
│   │   ├── consigfacil/scraper.py   # Scraper ConsigFácil (certificado digital)
│   │   ├── consigup/scraper.py      # Scraper ConsigUp (login/senha)
│   │   └── safeconsig/scraper.py    # Scraper SafeConsig (em desenvolvimento)
│   └── services/
│       ├── coleta_service.py        # Instancia scrapers e executa coletas
│       ├── comparador_service.py    # Detecta mudanças entre coletas
│       ├── orchestrator.py          # Coordena o fluxo completo de coleta
│       ├── scheduler.py             # Agenda execuções via APScheduler
│       └── notification/
│           ├── base.py              # Interface de notificação
│           ├── digest_builder.py    # Monta assunto e corpo HTML do e-mail
│           └── smtp.py              # Envio via SMTP
├── storage/
│   ├── repository.py                # Interfaces abstratas dos repositórios
│   └── file_storage.py              # Implementação em arquivo (JSON/JSONL)
├── tests/                           # Testes unitários (pytest)
├── data/                            # Dados persistidos em runtime (ignorado pelo git)
├── .env                             # Variáveis de ambiente (não versionado)
├── requirements.txt                 # Dependências Python
└── testar_smtp.py                   # Script manual de teste de e-mail
```

---

## Requisitos

- Python 3.11+
- Google Chrome instalado
- Playwright (instalado via pip + `playwright install`)
- Acesso ao servidor SMTP configurado

---

## Instalação

**1. Crie e ative o ambiente virtual:**

```bash
python -m venv env
```

Windows:
```powershell
env\Scripts\Activate.ps1
```

Linux/macOS:
```bash
source env/bin/activate
```

**2. Instale as dependências:**

```bash
pip install -r requirements.txt
```

**3. Instale os browsers do Playwright:**

```bash
playwright install chromium
```

Para usar o Chrome real (necessário para autenticação por certificado):

```bash
playwright install chrome
```

---

## Configuração

Copie o `.env` de exemplo e preencha com seus valores:

```bash
cp .env .env.local
```

Variáveis disponíveis:

```env
# --- Browser ---
HEADLESS=False               # True para rodar sem interface gráfica
TIMEOUT_MS=180000            # Timeout de operações Playwright em ms (padrão: 3 min)
CHROME_CHANNEL=chrome        # Canal do Chrome usado pelo Playwright

# --- Storage ---
STORAGE_PATH=data            # Diretório onde os dados são persistidos

# --- SMTP ---
SMTP_HOST=smtp.gmail.com     # Servidor SMTP
SMTP_PORT=587                # Porta SMTP (587 para TLS, 465 para SSL)
SMTP_USER=seu@email.com      # Usuário do SMTP
SMTP_PASSWORD=sua_senha      # Senha ou App Password
SMTP_USE_TLS=True            # Usar TLS (recomendado)

# --- Notificações ---
notification_DESTINATARIOS=analista@empresa.com,gestor@empresa.com

# --- Agendamento ---
COLETA_HORARIO=08:00         # Formato HH:MM. Deixe vazio para desabilitar.
```

> **Gmail:** Utilize uma [App Password](https://myaccount.google.com/apppasswords) em vez da senha principal. Requer 2FA ativado na conta.

> **Office 365:** Use `smtp.office365.com`, porta `587`, `SMTP_USE_TLS=True`.

---

## Configurando convênios

Os convênios são configurados em `app/core/processadoras.json`. O arquivo tem duas seções: `processadoras` (configuração técnica de cada processadora) e `convenios` (mapeamento de cada convênio para sua processadora).

### Adicionando um convênio ConsigFácil

ConsigFácil usa certificado digital instalado no perfil do Chrome. Não são necessárias credenciais no JSON.

```json
{
  "convenios": {
    "nome_do_convenio": {
      "nome": "Nome Exibido",
      "processadora": "consigfacil",
      "slug": "slug-do-convenio"
    }
  }
}
```

O slug é o identificador usado na URL do portal ConsigFácil. Exemplo: para `belterra`, a URL gerada é:

```
https://www.faciltecnologia.com.br/consigfacil/belterra/validar_certificado_cliente.php
```

Alguns convênios usam URL própria em vez de slug:

```json
{
  "mt": {
    "nome": "Portal do Consignado MT",
    "processadora": "consigfacil",
    "base_url": "https://portaldoconsignado.mt.gov.br/validar_certificado_cliente.php?novo_layout=On"
  }
}
```

### Adicionando um convênio ConsigUp

ConsigUp usa login e senha por convênio. As credenciais ficam no JSON:

```json
{
  "nome_do_convenio": {
    "nome": "Nome Exibido",
    "processadora": "consigup",
    "credentials": {
      "username": "seu_usuario",
      "password": "sua_senha"
    },
    "base_url": "https://sistema.consigup.com.br/Login.aspx"
  }
}
```

> **Atenção:** Não versione credenciais reais no JSON. Considere usar variáveis de ambiente referenciadas no loader para produção.

---

## Subindo a API

```bash
env/Scripts/python.exe -m uvicorn app.api.main:app --reload
```

A API sobe em `http://localhost:8000`. Ao iniciar, o scheduler é configurado automaticamente com base na variável `COLETA_HORARIO`.

Documentação interativa (Swagger UI): `http://localhost:8000/docs`

---

## Endpoints

### `GET /health`

Verifica se a API está no ar.

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

### `POST /coletas/{processadora}/executar`

Dispara uma coleta imediata para a processadora especificada. Equivalente a acionar o scheduler manualmente.

```bash
curl -X POST http://localhost:8000/coletas/consigfacil/executar
```

Resposta:

```json
{
  "id": "uuid-da-execucao",
  "processadora": "consigfacil",
  "status": "ok",
  "executada_em": "2026-05-05T08:00:00",
  "total_convenios": 10,
  "success_count": 10,
  "error_count": 0
}
```

Possíveis valores de `status`:

| Valor | Significado |
|---|---|
| `ok` | Todos os convênios coletados com sucesso |
| `partial_success` | Parte dos convênios coletou, outros falharam |
| `erro` | Nenhum convênio coletou |

---

### `GET /coletas/{processadora}/execucoes`

Lista o histórico de execuções de uma processadora, da mais recente para a mais antiga.

```bash
curl http://localhost:8000/coletas/consigfacil/execucoes
```

---

### `GET /coletas/{processadora}/dados`

Retorna os dados da última execução bem-sucedida — as datas de corte atuais de cada convênio.

```bash
curl http://localhost:8000/coletas/consigfacil/dados
```

Resposta:

```json
[
  {
    "convenio_key": "belterra",
    "convenio_nome": "Belterra",
    "folha": "FOLHA 02",
    "mes_atual": "05/2026",
    "data_corte": "10/05/2026"
  }
]
```

---

### `POST /notification/testar`

Envia um e-mail de teste usando a configuração SMTP do `.env`. Útil para validar a configuração antes de depender do sistema em produção.

```bash
curl -X POST http://localhost:8000/notification/testar
```

Respostas possíveis:

| Status | Situação |
|---|---|
| `200` | E-mail enviado com sucesso |
| `422` | `SMTP_HOST` ou `notification_DESTINATARIOS` não configurados |
| `500` | Falha de conexão com o servidor SMTP |

---

## Agendamento automático

O serviço usa APScheduler embutido — não precisa de cron externo nem de Celery.

Configure a variável `COLETA_HORARIO` no `.env`:

```env
COLETA_HORARIO=08:00
```

Ao subir a API, o scheduler agenda uma coleta para **todas as processadoras** configuradas no `processadoras.json` no horário especificado. Para desabilitar o agendamento, deixe a variável vazia:

```env
COLETA_HORARIO=
```

O horário aceita apenas o formato `HH:MM` (24h). Valores fora do range válido (ex: `25:99`) são rejeitados com log de erro.

---

## Testes

Os testes cobrem: modelos de domínio, storage em arquivo, comparador de datas, orquestrador, scheduler e endpoints da API.

**Rodar todos os testes:**

```powershell
cd monitor-data-corte
env\Scripts\python.exe -m pytest tests/ -v
```

**Rodar um grupo específico:**

```powershell
env\Scripts\python.exe -m pytest tests/services/ -v
env\Scripts\python.exe -m pytest tests/storage/ -v
env\Scripts\python.exe -m pytest tests/api/ -v
```

> Use sempre o Python do ambiente virtual (`env\Scripts\python.exe`). O Python do sistema pode não ter as dependências instaladas.

Cobertura atual: **49 testes**.

| Módulo | Testes |
|---|---|
| `tests/api/` | Endpoint de teste SMTP (422, 500, 200) |
| `tests/core/` | Modelos e enums |
| `tests/services/` | Orquestrador, comparador, scheduler, digest de e-mail |
| `tests/storage/` | Leitura e escrita de execuções, dados de corte e eventos |

---

## Storage — onde os dados ficam

Os dados são persistidos em arquivos dentro do diretório `data/` (configurável via `STORAGE_PATH`):

```
data/
├── processadoras/
│   └── consigfacil/
│       ├── execucoes/
│       │   ├── {uuid}.json      # Uma execução por arquivo
│       │   └── ...
│       └── eventos/
│           └── 2026-05-05.jsonl # Eventos do dia (append)
└── dados_corte/
    └── {execucao_id}.json       # Dados coletados por execução
```

### Execução (`execucoes/{uuid}.json`)

```json
{
  "id": "uuid",
  "processadora": "consigfacil",
  "executada_em": "2026-05-05T08:00:00",
  "status": "ok",
  "total_convenios": 10,
  "success_count": 10,
  "error_count": 0,
  "erros": []
}
```

O campo `erros` lista os convênios que falharam com o motivo:

```json
"erros": [
  {
    "convenio_key": "belterra",
    "convenio_nome": "Belterra",
    "status": "erro",
    "erro": "Timeout ao aguardar tabela"
  }
]
```

### Dados de corte (`dados_corte/{execucao_id}.json`)

```json
[
  {
    "id": "uuid",
    "execucao_id": "uuid-da-execucao",
    "convenio_key": "belterra",
    "convenio_nome": "Belterra",
    "folha": "FOLHA 02",
    "mes_atual": "05/2026",
    "data_corte": "10/05/2026",
    "coletado_em": "2026-05-05T08:00:00"
  }
]
```

### Eventos (`eventos/YYYY-MM-DD.jsonl`)

Cada linha é um evento JSON:

```json
{"id": "uuid", "tipo": "data_corte_alterada", "processadora": "consigfacil", "convenio_key": "belterra", "data_corte_anterior": "10/05/2026", "data_corte_nova": "08/05/2026", "detectado_em": "2026-05-05T08:00:00"}
```

Tipos de evento:

| Tipo | Significado |
|---|---|
| `data_corte_alterada` | A data de corte mudou em relação à coleta anterior |
| `registro_novo` | Convênio apareceu pela primeira vez (ou após ausência) |
| `registro_nao_encontrado` | Convênio estava na coleta anterior mas não foi encontrado agora |

---

## Testando SMTP manualmente

Além do endpoint `/notification/testar`, há um script de linha de comando que lê as configurações do `.env`:

```bash
python testar_smtp.py
```

Se `SMTP_HOST` ou `notification_DESTINATARIOS` não estiverem configurados, o script encerra com mensagem de erro. Se o envio falhar, a exceção do SMTP é exibida integralmente.
