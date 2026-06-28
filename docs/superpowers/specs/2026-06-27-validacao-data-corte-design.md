# Spec — Validação de `data_corte` (Fase 4 #1)

Data: 2026-06-27 · Branch: feat/registro-falha-coleta · Status: design aprovado

## Contexto
`utils/dates.normalizar_data_corte` só faz **parsing**: se não casa nenhum padrão, devolve a
**string crua** (linha 60). O `comparador` compara strings — então um scrape que quebra e
retorna `"ver tabela"` no lugar de `10/05/2026` dispara um **falso `DATA_CORTE_ALTERADA`**
("a data mudou!"). Dado real do corpus: 330 `DD/MM/YYYY`, 10 `None`, 1 `MM/YYYY` (competência
SafeConsig — estimativa legítima).

## Objetivo
Validar `data_corte`; quando o valor coletado for **inválido (garbage)**, NÃO tratar como
mudança de data — emitir um **sinal de qualidade tipado** (`valor_invalido`, acionável).

## Decisões (aprovadas)
- **Janela plausível:** `DD/MM/YYYY` válida = data de calendário real **e** ano em
  `[ano_coleta-1 .. ano_coleta+1]`. `MM/YYYY` (competência/estimativa) também é válido.
- **Inválido:** categoria nova **`valor_invalido`** (acionável, "conferir"), distinta de `sem_dado`.

## Design
### 1. `utils/dates.validar_data_corte(valor, coletado_em) -> bool` (pura)
- `None`/vazio → `False`.
- `MM/YYYY` com mês 1–12 e ano plausível → `True` (competência).
- `DD/MM/YYYY` que seja data real (rejeita `31/02`) e ano em `[ano_coleta±1]` → `True`.
- Qualquer outra coisa → `False`.
- O ano de referência vem de `coletado_em` (parse ISO); **sem `datetime.now()` interno** —
  sem `coletado_em` parseável, a janela de ano é dispensada (ainda valida formato/calendário).

### 2. Comparador — gate na camada de DADOS (`comparar`)
No loop de `mapa_atual`, **antes** de REGISTRO_NOVO / DATA_CORTE_ALTERADA: se
`atual.data_corte` não é None e `validar_data_corte(atual.data_corte, ano(atual.coletado_em))`
é `False` → emite `ERRO_COLETA` categoria `valor_invalido` e `continue` (não vira novo nem
mudança, e o garbage não dispara "data alterada").

### 3. Categoria + e-mail
- `erro_classifier`: add `valor_invalido` em `CATEGORIAS` + `CATEGORIA_FRASE`
  ("valor de data inválido — conferir a coleta").
- `digest_builder`: grupo `valor_invalido` (extraído de `reais`) numa **seção de topo
  acionável** ("⚠️ Valor de data inválido — conferir"), em `_precisa_acao` → assunto `[Ação]`.

## Arquivos
| Arquivo | Mudança |
|---|---|
| `app/utils/dates.py` | `validar_data_corte` |
| `app/services/comparador_service.py` | gate na camada de dados → `valor_invalido` |
| `app/services/erro_classifier.py` | categoria + frase `valor_invalido` |
| `app/services/notification/digest_builder.py` | grupo + seção de topo + `_precisa_acao` |

## Testes (TDD, mock — sem DB)
- `validar_data_corte`: `10/05/2026`✓ (ano_ref 2026), `31/02/2026`✗, `06/2026`✓, `"ver tabela"`✗,
  `None`✗, `10/05/2099`✗ (ano fora), `10/05/2025`✓ (ano-1).
- comparador: anterior `10/05/2026` → atual `"ver tabela"` ⇒ **não** emite `DATA_CORTE_ALTERADA`;
  emite `ERRO_COLETA`/`valor_invalido`. Atual válido diferente ⇒ `DATA_CORTE_ALTERADA` (inalterado).
- digest: evento `valor_invalido` → seção "conferir" no topo + assunto `[Ação]`.

## Fora de escopo
- Reconciliação (valor improvável vs histórico) e flag `origem`/`confiança` — itens seguintes.
- Filtrar garbage de `/cortes/atuais` (display) — follow-up.
