# Contexto da feature: Janela de acesso de coleta do ConsigUp

> Documento de handoff para outra IA/engenheiro. Descreve **tudo o que foi feito**
> nesta feature, o estado atual do código e o que falta decidir.
> Repo: `monitor-data-corte` · Branch: `feat/registro-falha-coleta` · Data: 2026-06-26.

---

## 1. Resumo (o quê e por quê)

O portal **ConsigUp** (`sistema.consigup.com.br`) **só permite acesso em dias úteis,
das 08:00 às 17:00** (fuso `America/Sao_Paulo`). Antes desta feature, quando a coleta
rodava fora desse horário, o convênio **`muana`** (único convênio da processadora
`consigup`, "PREF DE MUANA - PA") falhava como qualquer erro técnico:

- virava **falha acionável** no topo do e-mail (alarme falso — não há o que consertar);
- a **retentativa de 60min** do runner podia disparar ainda mais tarde, **martelando o
  portal fora de hora** e usando a credencial;
- desperdiçava uma execução de Playwright/login que ia falhar de qualquer jeito.

A feature ensina o sistema a **não tentar** coletar o ConsigUp fora da janela e a tratar
isso como **pendência informativa** (rodapé do e-mail), não como falha.

### Decisões de negócio (fechadas com o dono do produto)

| Decisão | Valor |
|---|---|
| Janela | **Seg–sex, 08:00–17:00**, fuso `America/Sao_Paulo` |
| Margem de segurança | Corte efetivo **16:45** (15 min antes das 17h), pra não iniciar coleta que cruze as 17h |
| Fim de semana | **Não coleta** (sáb/dom = fora da janela) |
| Fora da janela | **Pula sem tocar o portal** (não constrói auth/scraper, não loga) + **pendência no rodapé** do e-mail, sem `[Ação]` |
| Escopo | **Específico do consigup** — não é um sistema genérico de janelas; outras processadoras nunca são puladas |
| Retry / agendamento | **Não alterados** como tarefa; mas o skip per-tentativa já impede martelar o portal no retry |

---

## 2. Estado atual

- **Implementada, testada e revisada.** Suíte: **110 passed, 10 skipped** (era 96 antes
  da feature — zero regressão).
- **NADA COMMITADO.** Todo o trabalho está no *working tree* da branch
  `feat/registro-falha-coleta`. O topo do log segue em `88490fb`.
- Há uma **spec** e um **plano** já escritos (também não commitados):
  - Spec: `docs/superpowers/specs/2026-06-26-consigup-janela-acesso-design.md`
  - Plano: `docs/superpowers/plans/2026-06-26-consigup-janela-acesso.md`

---

## 3. Arquitetura / fluxo do desfecho `fora_janela`

O princípio central: **a janela é checada no momento de cada tentativa, antes do login,
no funil único de coleta** (`executar_coleta_lote`). Assim a regra cobre a tentativa
inicial, a retentativa de 60min e o "coletar agora" da API — todos passam pelo mesmo
ponto. Fora da janela, **nem o navegador é aberto**.

`fora_janela` é um **terceiro desfecho**, distinto de `ok` e de `erro`. Fluxo ponta-a-ponta:

1. **`coleta_service.executar_coleta_lote`** — no loop por convênio, antes de construir
   auth/scraper: se `processadora == "consigup"` e `not dentro_da_janela_consigup()`,
   monta um resultado com `status="fora_janela"` e `continue` (não toca o portal).
2. **`_calcular_status_lote`** — convênios `fora_janela` não contam como sucesso nem como
   falha; se todos forem `fora_janela`, o status do lote é `fora_janela` (não `erro`).
   O dict do lote ganha `fora_janela_count`; `error_count` exclui os `fora_janela`.
3. **`orchestrator.coletar`** — mapeia `status="fora_janela"` para um efetivo
   `"fora_janela"` (não cai no `"erro"` genérico) e **exclui** o convênio da lista
   `erros_convenios` (não polui `Execucao.erros`).
4. **Sem retry** — duas camadas, ambas tratadas:
   - Runner diário (`run_daily_collection.py`): retenta por `status == ERROR`; como o lote
     fica `fora_janela`, **não dispara**.
   - Retry rápido do orchestrator (`_erros_tecnicos_retentaveis`): **exclui explicitamente**
     `fora_janela` (correção feita na revisão — ver §6).
5. **`comparador_service._comparar_status`** — emite um evento `ERRO_COLETA` com
   `categoria="fora_janela"`, `subtipo="fora_janela"`.
6. **`digest_builder`** — roteia esse evento para uma subseção de **rodapé**
   *"Fora da janela de acesso (coleta adiada)"*, fora de "Falhas novas" (topo) e de
   "Falhas conhecidas". Não marca `[Ação]` no assunto.

---

## 4. Arquivos alterados (11 arquivos, +219/−9)

### Novos
- **`app/services/janela_coleta.py`** — helper escopado ao consigup:
  - `dentro_da_janela_consigup(agora: datetime | None = None) -> bool`: `True` se dia útil
    (`weekday() < 5`) **e** `08:00 <= hora < 16:45`.
  - `PROCESSADORA = "consigup"`, `_agora_local()` (relógio patchável nos testes),
    constantes `JANELA_INICIO`/`JANELA_FIM`/`MARGEM_MIN`.
  - Fuso: `zoneinfo("America/Sao_Paulo")` com **fallback** para `timezone(-03:00)` se
    `tzdata` não estiver disponível (relevante no Windows).
- **`tests/services/test_janela_coleta.py`** — 8 testes (bordas 16:44/16:45, antes das 08h,
  pós-17h, sábado, domingo, e o enum).
- **`tests/services/test_coleta_service_janela.py`** — 3 testes (pula fora da janela sem
  tocar portal; coleta normal dentro; **outra processadora não é pulada**).

### Modificados (app)
- **`app/core/enums.py`** — `CollectionStatus.FORA_JANELA = "fora_janela"`.
- **`app/services/coleta_service.py`** — import do helper; bloco de skip no loop de
  `executar_coleta_lote`; `_calcular_status_lote` e as contagens de retorno
  (`error_count` exclui `fora_janela`, novo `fora_janela_count`).
- **`app/services/erro_classifier.py`** — `"fora_janela"` em `CATEGORIAS` e a frase em
  `CATEGORIA_FRASE` ("fora da janela de acesso do portal — coleta adiada").
  `classificar_erro` **não** muda (a categoria é setada pelo comparador, não derivada da string).
- **`app/services/comparador_service.py`** — ramo `fora_janela` em `_comparar_status`.
- **`app/services/orchestrator.py`** — em `coletar`: mapeamento de `status_atual` e exclusão
  de `erros_convenios`; em `_erros_tecnicos_retentaveis`: exclusão de `fora_janela` do retry.
- **`app/services/notification/digest_builder.py`** — `_categorizar` (grupo `fora_janela`,
  excluído de `reais`) e `_montar_corpo` (subseção de rodapé).

### Modificados (testes)
- **`tests/services/test_comparador_service.py`** — +1 teste (evento `fora_janela`).
- **`tests/services/notificacao/test_digest_builder.py`** — +1 teste (rodapé, sem `[Ação]`).

**Total: 14 testes novos.**

---

## 5. Como rodar / verificar (sem tocar o portal)

```bash
# da raiz do repo (Git Bash); usa o venv do projeto
./env/Scripts/python.exe -m pytest -q                         # suíte: 110 passed, 10 skipped
./env/Scripts/python.exe -m pytest tests/services/test_janela_coleta.py -q
```

Todos os testes usam relógio/scraper mockados — **nenhum** toca o portal real. Não rode
nada contra `sistema.consigup.com.br` (a credencial está em rotação; ver §7).

---

## 6. Revisão e correção

A execução foi feita em modo *subagent-driven* (um subagente por tarefa, TDD). Uma
**revisão final independente** encontrou **1 furo Important**: o desfecho `fora_janela`
vazava para o retry rápido do orchestrator (`_erros_tecnicos_retentaveis`), que o
classificava como "erro técnico retentável" — fazendo o lote re-rodar e logar
`WARNING: Retentativa N/2 ... erro técnico: muana` em toda rodada fora de hora (sem tocar
o portal, mas re-emitindo o alarme falso que a feature existe pra eliminar).

**Corrigido**: `_erros_tecnicos_retentaveis` agora exclui `status in ("ok", "fora_janela")`.
Travado com `test_fora_janela_nao_retenta`.

### Itens Minor conhecidos (aceitos / diferidos)
- **Resumo do runner** (`run_daily_collection.py`) reporta a processadora pulada como `✓ ok`
  (só `PARTIAL_SUCCESS` é tratado à parte). Por design — o canal de aviso é o rodapé do
  e-mail. Mildly enganoso no JSON/print de ops.
- **Fuso / fallback** (`_agora_local` / `zoneinfo`→offset) **não é exercitado por teste**
  (os testes passam `datetime` explícito). Diferido para verificação manual.
- `_corte_efetivo()` recomputa 16:45 a cada chamada (vs. constante de módulo) — inofensivo.

---

## 7. Contexto de segurança (IMPORTANTE, em aberto)

A credencial do **muana/consigup** (par usuário+senha) está **exposta no histórico do git**:
ficou embutida em texto puro no `app/core/processadoras.json` em commits antigos
(**`f118f85`** de 2026-04-27 e **`4fbebbb`** de 2026-04-30), depois refatorada para
`credential_env_key` (o HEAD atual está limpo). O **GitGuardian** detectou (Authentication
Tuple). Esses commits são ancestrais de `origin/main` **e** de
`origin/feat/registro-falha-coleta`.

Remediação **pendente** (decisão do dono): **(1) rotacionar a senha do muana no portal
ConsigUp** + **(2) purgar o blob do histórico** (filter-repo) em ambas as branches e
force-push. Esta feature **reduz** o uso do portal fora de hora, mas **não substitui** a
rotação.

> Implicação para commit: como a branch ainda vai sofrer reescrita de histórico, considerar
> resolver a remediação **antes** de empilhar/pushar commits novos (ou commitar local sem push).

---

## 8. O que falta decidir (handoff)

1. **Como/quando commitar** a feature (nada commitado ainda). Opções: segurar até a
   remediação de segurança; commit único `feat(consigup): janela de acesso…`; ou os 4
   commits separados do plano (split por hunk).
2. **Sequência com a segurança**: rotacionar a credencial do muana + limpar histórico —
   idealmente antes de pushar qualquer coisa.

---

## 9. Referências

- Spec (design aprovado): `docs/superpowers/specs/2026-06-26-consigup-janela-acesso-design.md`
- Plano de implementação (4 tarefas TDD): `docs/superpowers/plans/2026-06-26-consigup-janela-acesso.md`
- Funções-chave: `app/services/janela_coleta.py:dentro_da_janela_consigup`,
  `app/services/coleta_service.py:executar_coleta_lote` (bloco de skip),
  `app/services/orchestrator.py:_erros_tecnicos_retentaveis` (guard do retry).
