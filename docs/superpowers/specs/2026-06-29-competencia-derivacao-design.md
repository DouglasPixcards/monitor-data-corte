# Spec — Definição de competência por convênio (offset validado)

Data: 2026-06-29 · Branch: feat/registro-falha-coleta · Status: design aprovado · run

## Objetivo
Definir e exibir a **competência** que cada data de corte fecha, no calendário/painel. Como a
competência não sai da data sozinha (depende da convenção do convênio), usamos um **offset por
convênio** — o número de meses entre o mês do corte e a competência — **validado manualmente
uma vez** e aplicado automaticamente daí em diante.

## Seed (validado pelo usuário, 2026-06-29)
- Offset **0** para quase todos (competência = mês do corte).
- Offset **+1** para `duque_de_caxias_rj` e `IPMDC` (corte de julho fecha agosto).
- Prova de que o offset é por-convênio: `cotia_sp` e `IPMDC` (ambos consiglog, corte 20/07)
  fecham competências diferentes (07 vs 08).
- SafeConsig (API): a data de corte estimada já cai no mês da competência → offset 0.

## Design
- **`app/utils/dates.py:derivar_competencia(data_corte, offset=0)`** (pura): mês/ano do corte
  (DD/MM/YYYY ou MM/YYYY) + `offset` meses (com virada de ano) → `"MM/YYYY"`. None se não parseável.
- **Config:** `competencia_offset` no convênio (`processadoras.json`); default 0. Só `duque_de_caxias_rj`
  e `IPMDC` recebem `1`.
- **`/cortes/atuais`** (`_montar_dados_convenios`): expõe `competencia` por linha =
  `derivar_competencia(data_corte, convenio.competencia_offset)`.
- **Painel:** competência mostrada na linha do board e em cada corte do calendário.

## Testes
- `derivar_competencia`: offset 0/+1/-1, virada de ano, MM/YYYY, None p/ garbage.
- `/cortes/atuais` expõe `competencia` (com e sem offset).

## Follow-ups
- Cross-check: comparar a competência derivada com a que a API do SafeConsig devolve (hoje
  descartada no collector) — alerta se divergir.
- Re-validar o offset se o monitor detectar competência divergente numa coleta futura.
