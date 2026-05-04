# Design — Pipeline de Coleta de Datas de Corte

**Data:** 2026-04-29
**Módulo:** `monitor-data-corte`
**Escopo:** Redesenho do pipeline de comparação e alerta para as 3 processadoras existentes (ConsigFácil, SafeConsig, ConsigUp)

---

## 1. Contexto

O módulo de coleta de datas de corte já possui infraestrutura de scraping funcional (3 scrapers), storage em arquivo e módulos de comparação e eventos. Porém, comparação, eventos e notificação estão desconectados do fluxo principal — a coleta acontece, o snapshot é salvo, mas nenhuma comparação é executada, nenhum evento é persistido e nenhum alerta é enviado.

Este design cobre o redesenho dessas peças de forma coesa, com modelos de domínio tipados e interfaces preparadas para migração futura a banco de dados relacional (PostgreSQL via Docker).

---

## 2. Decisões de arquitetura

| Decisão | Escolha | Motivo |
|---|---|---|
| Padrão de pipeline | Orquestrador de serviços | Separação de responsabilidades sem complexidade de event bus |
| Storage atual | Arquivo (JSON) | Suficiente para o momento; interface DB-ready para migração |
| Modelos de domínio | `dataclass` tipados | Mapeia diretamente para tabelas futuras |
| Notificação | E-mail SMTP, digest por execução | Simples, sem dependência externa; abstrato para troca futura |
| Trigger | Manual via API agora; APScheduler futuramente | APScheduler já considerado no design do orquestrador |
| Retenção de dados | Nada é deletado | Todo histórico é mantido para auditoria |

---

## 3. Estrutura de arquivos

```
monitor-data-corte/
└── app/
    ├── api/
    │   └── main.py                  # FastAPI — endpoints de trigger e consulta
    │
    ├── core/
    │   ├── enums.py                 # EventoTipo, CollectionStatus
    │   ├── models.py                # Execucao, DadoCorte, Evento (dataclasses)
    │   ├── settings.py              # Configurações via env vars
    │   └── processadoras.json       # Config de processadoras e convênios
    │
    ├── scrapers/                    # Sem mudança
    │   ├── base_scraper.py
    │   ├── consigfacil/
    │   ├── safeconsig/
    │   └── consigup/
    │
    ├── services/
    │   ├── coleta_service.py        # Sem mudança — constrói e roda scrapers
    │   ├── comparador_service.py    # Redesenhado — recebe listas de DadoCorte, retorna list[Evento]
    │   ├── orchestrator.py          # NOVO — coordena o pipeline completo
    │   └── notification/
    │       ├── base.py              # NotificadorBase (ABC)
    │       ├── smtp.py              # EmailSMTPNotificador
    │       └── digest_builder.py    # Monta assunto + corpo HTML do digest
    │
    └── storage/
        ├── repository.py            # Interfaces: ExecucaoRepository, DadosCorteRepository, EventoRepository
        └── file_storage.py          # Implementações em arquivo (sem conceitos de arquivo na interface)
```

---

## 4. Modelos de domínio

```python
# app/core/models.py

@dataclass
class Execucao:
    id: str
    processadora: str
    executada_em: str        # ISO 8601
    status: str              # "ok" | "erro" | "partial_success"
    total_convenios: int
    success_count: int
    error_count: int

@dataclass
class DadoCorte:             # → tabela dados_corte (futura)
    id: str
    execucao_id: str
    convenio_key: str
    convenio_nome: str
    folha: str | None
    mes_atual: str | None
    data_corte: str | None
    coletado_em: str         # ISO 8601

@dataclass
class Evento:                # → tabela eventos (futura)
    id: str
    tipo: str                # EventoTipo enum
    processadora: str
    convenio_key: str
    execucao_id: str
    detectado_em: str        # ISO 8601
    folha: str | None
    mes_atual: str | None
    data_corte_anterior: str | None   # None para REGISTRO_NOVO
    data_corte_nova: str | None       # None para REGISTRO_NAO_ENCONTRADO
```

---

## 5. Tipos de evento

```python
# app/core/enums.py

class EventoTipo(str, Enum):
    DATA_CORTE_ALTERADA     = "data_corte_alterada"       # dispara notificação
    REGISTRO_NOVO           = "registro_novo"              # só audit log
    REGISTRO_NAO_ENCONTRADO = "registro_nao_encontrado"   # só audit log
    ERRO_COLETA             = "erro_coleta"                # só audit log
```

### Regras de preenchimento por tipo

| Campo | `data_corte_alterada` | `registro_novo` | `registro_nao_encontrado` |
|---|---|---|---|
| `data_corte_anterior` | valor antigo | `None` | valor que existia |
| `data_corte_nova` | valor novo | valor coletado | `None` |
| `folha` / `mes_atual` | preenchidos | preenchidos | preenchidos |

### O que cada tipo faz

| Tipo | Audit log | E-mail |
|---|---|---|
| `DATA_CORTE_ALTERADA` | sim | sim — entra no digest |
| `REGISTRO_NOVO` | sim | não |
| `REGISTRO_NAO_ENCONTRADO` | sim | não |
| `ERRO_COLETA` | sim | não |

---

## 6. Interfaces de repositório

As interfaces não expõem nenhum conceito de arquivo. Quando o banco vier, basta uma nova implementação.

```python
# app/storage/repository.py

class ExecucaoRepository(ABC):
    def salvar(self, execucao: Execucao) -> None: ...
    def buscar_ultima_ok(self, processadora: str) -> Execucao | None: ...
    def listar(self, processadora: str) -> list[Execucao]: ...

class DadosCorteRepository(ABC):
    def salvar_lote(self, dados: list[DadoCorte]) -> None: ...
    def buscar_por_execucao(self, execucao_id: str) -> list[DadoCorte]: ...

class EventoRepository(ABC):
    def salvar_lote(self, eventos: list[Evento]) -> None: ...
```

---

## 7. Fluxo do orquestrador

```python
# app/services/orchestrator.py

class ColetaOrchestrator:
    def __init__(
        self,
        execucao_repo: ExecucaoRepository,
        dados_repo: DadosCorteRepository,
        evento_repo: EventoRepository,
        comparador: ComparadorService,
        notificador: NotificadorBase,
        destinatarios: list[str],
    ): ...

    def executar(self, processadora: str) -> Execucao:
        # 1. Carregar dados anteriores ANTES de salvar qualquer coisa
        #    (garante que buscar_ultima_ok retorna a execução anterior, não a atual)
        ultima_execucao_ok = self.execucao_repo.buscar_ultima_ok(processadora)
        dados_anteriores = (
            self.dados_repo.buscar_por_execucao(ultima_execucao_ok.id)
            if ultima_execucao_ok else []
        )

        # 2. Rodar scrapers
        resultado_lote = coleta_service.executar_coleta_lote(processadora)

        # 3. Determinar status da execução e salvar
        status = resultado_lote["status"]  # "ok" | "erro" | "partial_success"
        execucao = Execucao(id=..., processadora=processadora, status=status, ...)
        self.execucao_repo.salvar(execucao)

        # 4. Converter apenas registros coletados com sucesso em DadoCorte tipados
        #    (convênios com erro não entram na comparação — evita falsos positivos)
        dados_atuais = [
            DadoCorte(...) for record in resultado_lote["records"]
        ]
        self.dados_repo.salvar_lote(dados_atuais)

        # 5. Comparar e gerar eventos
        eventos = self.comparador.comparar(
            processadora=processadora,
            execucao_id=execucao.id,
            anteriores=dados_anteriores,
            atuais=dados_atuais,
        )
        self.evento_repo.salvar_lote(eventos)

        # 6. Notificar se houver mudanças de data de corte
        mudancas = [e for e in eventos if e.tipo == EventoTipo.DATA_CORTE_ALTERADA]
        if mudancas:
            assunto, corpo = DigestBuilder.build(processadora, mudancas)
            try:
                self.notificador.enviar(assunto, self.destinatarios, corpo)
            except Exception:
                pass  # falha no e-mail não desfaz o que foi salvo

        return execucao
```

### Regras do fluxo

- Os dados da execução anterior são carregados **antes** de qualquer escrita — garante que `buscar_ultima_ok` sempre retorna a execução anterior, nunca a atual
- O status da `Execucao` é determinado pelo `resultado_lote`: `"ok"`, `"erro"` ou `"partial_success"`
- Apenas convênios coletados com sucesso entram em `dados_atuais` — convênios que falharam não geram eventos de `REGISTRO_NAO_ENCONTRADO` (seria falso positivo)
- Uma falha no envio de e-mail é absorvida — não desfaz snapshot, dados ou eventos já salvos
- Nenhum dado é jamais deletado — `DadoCorte` e `Evento` só acumulam

---

## 8. Camada de notificação

### Interface

```python
# app/services/notification/base.py

class NotificadorBase(ABC):
    @abstractmethod
    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None: ...
```

### Implementação SMTP

```python
# app/services/notification/smtp.py

class EmailSMTPNotificador(NotificadorBase):
    def __init__(self, host: str, port: int, user: str, password: str, use_tls: bool = True): ...
    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None: ...
```

### Variáveis de ambiente necessárias

```
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_USE_TLS=true
notification_DESTINATARIOS=ana@empresa.com,joao@empresa.com
```

### Formato do digest

```
Assunto:
  [Alerta] Mudança de data de corte — ConsigFácil (3 alterações)

Corpo HTML:
  Processadora: ConsigFácil
  Executado em: 29/04/2026 08:00

  Alterações detectadas:
  | Convênio   | Folha       | Antes      | Depois     |
  |------------|-------------|------------|------------|
  | Belterra   | FOLHA 02/26 | 10/05/2026 | 08/05/2026 |
  | Maranhão   | FOLHA 02/26 | 12/05/2026 | 10/05/2026 |
```

---

## 9. API

```
POST /coletas/{processadora}/executar      → orchestrator.executar(processadora)
GET  /coletas/{processadora}/execucoes     → ExecucaoRepository.listar()
GET  /coletas/{processadora}/dados         → DadosCorteRepository.buscar_por_execucao(ultima_ok)
GET  /coletas/{processadora}/eventos       → EventoRepository (futuro)
GET  /health
```

---

## 10. APScheduler (futuro)

Quando o scheduler entrar, basta adicionar `app/scheduler.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def registrar_jobs(orchestrator: ColetaOrchestrator):
    for processadora in ["consigfacil", "safeconsig", "consigup"]:
        scheduler.add_job(
            orchestrator.executar,
            trigger="cron",
            hour=7,
            kwargs={"processadora": processadora},
            id=f"coleta_{processadora}",
        )
```

O `main.py` do FastAPI chama `scheduler.start()` no evento de startup. O orquestrador não muda nada.

---

## 11. O que não muda

- `BaseScraper` e os 3 scrapers existentes
- `coleta_service.py` (construção e execução de scrapers)
- `processadoras.json` (configuração de processadoras e convênios)
- Estratégias de autenticação (`certificate_auth.py`, `user_pass_auth.py`)

---

## 12. Fora do escopo deste design

- Migração para banco de dados relacional (PostgreSQL + Docker)
- APScheduler (mencionado, mas implementação posterior)
- Expansão para as demais ~23 processadoras
- Calendário de corte para o módulo de remessas
- Interface de fallback manual para entrada de datas
