# Spec — Métricas de coleta (Fase 5 / observabilidade)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (run autônomo)

## Objetivo
Visibilidade operacional: **taxa de sucesso por processadora** (com tendência) e **quais
convênios estão falhando**, a partir do que já é persistido (Execucao + eventos).

## Design (reusa os repositórios; sem mudança de modelo/migration)
- **`app/services/metricas.py`** (puro):
  - `resumo_processadora(execucoes, limite=10)` → `taxa_atual`, `taxa_media`, `tendencia`,
    `execucoes`, `ultima_em`. Denominador = **`success_count + error_count`** (= ok + erros
    reais), que **exclui `fora_janela`** — senão um run fora da janela (ConsigUp no fim de
    semana) baixaria a taxa pra 0% falsamente. Runs 100% fora_janela (considerados=0) são
    ignorados. Tendência = taxa da metade recente vs a antiga (±0.05; `<4` execuções = estável).
  - `falhas_por_convenio(eventos)` → conta `ERRO_COLETA` por convênio, **excluindo** categorias
    não-acionáveis (`fora_janela`, `nao_executou`, `falha_conhecida`, `valor_invalido`,
    `salto_suspeito`) — só o que o operador pode agir (auth/credencial/rede/timeout/portal/…).
- **`GET /metricas`**: por processadora chama `execucao_repo.listar` + `evento_repo.listar(dias=30)`,
  agrega → `{processadoras:[...], convenios_com_falha:[...]}` (este com `processadora`).
- **Painel:** 3ª aba **Métricas** — barras de taxa por processadora (verde/amarelo/vermelho,
  neutra p/ sem-dados) + lista de convênios com falha (categoria · subtipo · contagem).

## Testes
- `resumo_processadora`: taxa atual/média, limite, tendência ↑/↓, **fora_janela não zera**,
  só-fora_janela = sem_dados. `falhas_por_convenio`: conta/ordena, ignora não-ERRO_COLETA e
  **categorias não-acionáveis**, mantém categoria mais recente. Endpoint via TestClient.

## Follow-ups (menores, anotados)
- `listar` carrega histórico inteiro p/ usar só as 10 mais recentes (add `limite` no repo).
- Tie-break determinístico da "categoria mais recente" entre file/postgres (secundário por id).
- Separar "falhas conhecidas vs novas" em vez de só ocultar conhecidas, se quiser visibilidade.
