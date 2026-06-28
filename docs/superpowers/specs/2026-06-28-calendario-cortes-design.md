# Spec — Calendário de cortes (Fase 5)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (run autônomo)

## Objetivo
Além do board, uma **vista de calendário** mensal: ver de relance em que dias do mês caem as
datas de corte e quais convênios vencem em cada dia.

## Design (pure frontend — reusa `/cortes/atuais`, sem mudança de backend)
- **`lib.js:cortesPorDia(dados, ano, mes)`** → `Map<dia, convênios[]>` dos cortes cuja `data_corte`
  (`DD/MM/YYYY`, via `parseBR`) cai em (ano, mês). Linhas sem data precisa (`MM/YYYY`/vazio) ficam
  fora do calendário.
- **`App.jsx`:**
  - Toggle **Board / Calendário** nos controles.
  - `Calendario`: grade mensal (cabeçalho dom–sáb + células de dia), com navegador de mês
    (‹ mês atual ›). Cada célula com corte mostra o **nº de convênios** e a lista (nome) do dia;
    o dia de hoje é destacado.
- **`styles.css`:** grade do calendário + destaque de hoje + células com corte.

## Testes
- `cortesPorDia`: agrupa por dia certo no mês/ano dados; ignora `MM/YYYY`/None/outro mês.
  (Lógica de data é o único ponto com risco — off-by-one de mês.)

## Fora de escopo
- Backend de calendário (agrupamento é client-side) · arrastar/editar · exportar .ics — depois.
