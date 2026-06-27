# Spec — Janela de acesso de coleta do ConsigUp

Data: 2026-06-26
Branch: feat/registro-falha-coleta
Status: design aprovado, aguardando revisão da spec

## Contexto

O portal ConsigUp (`sistema.consigup.com.br`) **só permite acesso até as 17h**
(fuso America/Sao_Paulo). Hoje não há nenhuma noção de janela horária no código
nem na config. Quando a coleta roda fora desse horário, o `muana` (único convênio
consigup, "PREF DE MUANA - PA") falha como qualquer outra falha técnica:

- vira **falha acionável** no topo do e-mail (alarme falso — não há o que consertar);
- a **retentativa de 60min** do runner (`run_daily_collection.py`) pode disparar
  ainda mais tarde, **martelando o portal fora do horário** e usando a credencial
  (que, além disso, está em rota de rotação por exposição);
- desperdiça uma execução de Playwright/login que vai falhar de qualquer jeito.

Objetivo: ensinar o sistema a **não tentar** coletar o consigup fora da janela, e a
tratar isso como **pendência informativa** (não falha), sem alarme.

## Requisitos (decididos com o usuário)

1. **Janela:** 08:00–17:00, fuso `America/Sao_Paulo`, **dias úteis (segunda a sexta)**.
   Fim de semana não coleta.
2. **Margem de segurança:** corte efetivo **16:45** (15 min antes das 17h), para não
   iniciar uma coleta que cruze as 17h.
3. **Fora da janela:** **pular sem tocar o portal** (não constrói scraper, não loga) +
   registrar como **pendência no rodapé** do e-mail (não acionável, não conta como erro).
4. **Escopo:** **específico do consigup** (não generalizar para um sistema de janelas
   reutilizável).
5. **Retry/agendamento:** **fora de escopo** — o usuário ajusta manualmente. Não
   alteramos a lógica de retry nem o `COLETA_HORARIO`.

## Princípio do design

A checagem da janela acontece **no momento de cada tentativa, antes do login**, no
**funil único de coleta** (`executar_coleta_lote`). Por consequência, a regra cobre a
tentativa inicial, a retentativa de 60min e o "coletar agora" da API — todas passam
pelo mesmo ponto. Isso resolve o risco de martelar o portal **sem precisar mexer no
retry**: uma retentativa fora da janela simplesmente pula de novo.

## Design

### 1. Helper de janela — `app/services/janela_coleta.py` (novo)

Escopado ao consigup, com constantes tunáveis e relógio **injetável** (testável):

```python
JANELA_INICIO = time(8, 0)
JANELA_FIM    = time(17, 0)
MARGEM_MIN    = 15           # corte efetivo 16:45
_TZ = ZoneInfo("America/Sao_Paulo")  # fallback: timezone(-03:00) se tzdata ausente

def _agora_local() -> datetime: ...        # datetime.now(_TZ) — patchável nos testes
def dentro_da_janela_consigup(agora=None) -> bool:
    # True se dia útil (weekday()<5) E JANELA_INICIO <= hora < (JANELA_FIM - MARGEM_MIN)
```

### 2. Skip no funil — `coleta_service.executar_coleta_lote`

No loop por convênio (`app/services/coleta_service.py`, ~linha 163), **antes** de
`build_auth_strategy` / `build_scraper` / `scraper.run()`:

> se `processadora_key == "consigup"` e `not dentro_da_janela_consigup()` →
> monta `resultado_convenio` com **`status="fora_janela"`**, `records_count=0`,
> `dados=[]`, `erro="[ConsigUp] Fora da janela de acesso (08:00–16:45) — coleta pulada nesta rodada."`,
> loga em nível INFO e `continue` (não toca o portal).

### 3. Terceiro desfecho `fora_janela` (status e contagem)

`fora_janela` é um desfecho distinto de `ok` e `erro`:

- `_calcular_status_lote` (`coleta_service.py`, ~linha 122): convênios `fora_janela`
  **não contam como sucesso nem como falha**. Se todos os convênios de uma processadora
  forem `fora_janela`, o status do lote é **`fora_janela`** (novo), não `erro`.
- O dict de retorno do lote ganha `fora_janela_count`; `error_count` exclui os `fora_janela`.
- **Efeito colateral desejado:** o runner (`run_daily_collection.py`) decide retry por
  `execucao.status == ERROR`; como o lote não fica `erro`, **a retentativa de 60min não
  dispara** — sem alterar a lógica de retry.

### 4. Notificação — rodapé informativo

Fluxo `orchestrator.coletar` → `comparador_service` → `digest_builder`:

- `orchestrator.coletar` (montagem de `status_atual`): mapeia `status == "fora_janela"`
  para um efetivo **`"fora_janela"`** (em vez de cair no `"erro"` genérico).
- `comparador_service._comparar_status`: reconhece `fora_janela` → emite `ERRO_COLETA`
  com **`categoria="fora_janela"`** e um subtipo que roteia pro rodapé (modelo: o ramo
  `known_failure`/`conhecida`, mas com rótulo próprio).
- `erro_classifier`: nova `categoria "fora_janela"` em `CATEGORIAS` + frase em
  `CATEGORIA_FRASE` (ex.: *"fora da janela de acesso do portal — coleta adiada"*).
- `digest_builder`: nova subseção de **rodapé** *"Fora da janela de acesso (coleta adiada)"*,
  separada de "Falhas novas" (topo) e de "Falhas conhecidas". **Não** marca `[Ação]` no assunto.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `app/services/janela_coleta.py` | **novo** — janela + relógio injetável |
| `app/services/coleta_service.py` | skip no loop + `fora_janela` em `_calcular_status_lote` e contagens |
| `app/services/orchestrator.py` | `status_atual` mapeia `fora_janela` |
| `app/services/comparador_service.py` | evento de rodapé para `fora_janela` |
| `app/services/erro_classifier.py` | categoria + frase `fora_janela` |
| `app/services/notification/digest_builder.py` | subseção de rodapé |

## Testes (TDD)

- `tests/services/test_janela_coleta.py` (novo): dentro/fora da janela, borda da margem
  (16:44 dentro, 16:45 fora), antes das 08h, fuso.
- `coleta_service`: com relógio fora da janela, consigup → `fora_janela` e **scraper não
  construído** (patch/asserção de que `build_scraper`/`scraper.run` não é chamado); dentro
  da janela → coleta normal. Outras processadoras: nunca pulam.
- `digest_builder`: evento `fora_janela` cai no rodapé, assunto sem `[Ação]`.

## Fora de escopo (responsabilidade manual do usuário)

- Ajuste de `COLETA_HORARIO` / ordem de coleta. **Nota operacional:** o `16:08` atual
  está dentro da janela, mas perto da margem 16:45 — se a rodada atrasar ou o muana for
  tarde na fila, pode cruzar. Critério do usuário.
- Alteração de qualquer lógica de retry.

## Premissas e verificações

- **Fim de semana:** não coleta (sáb/dom contam como fora da janela). Decidido.
- **Verificação de implementação:** confirmar que `zoneinfo` resolve `America/Sao_Paulo`
  no Windows (Python 3.14 pode exigir o pacote `tzdata`); se não, usar offset fixo `-03:00`.

## Alternativa considerada (rejeitada)

Reusar `known_failure=True` no resultado do skip — daria rodapé + sem-retry com mudança
só no `coleta_service`. **Rejeitada** porque rotularia como *"falha conhecida (já mapeada)"*,
confundindo "pulado temporariamente, coleta amanhã no horário" com "convênio
permanentemente quebrado". A categoria `fora_janela` dedicada é mais clara para o operador.
