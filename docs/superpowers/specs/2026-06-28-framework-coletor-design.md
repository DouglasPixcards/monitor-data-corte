# Spec — Framework de coletor padronizado (validação declarativa + helpers)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (escopo A) · run autônomo

## Objetivo
Baratear adicionar/manter portais Playwright SIMPLES, sem brigar com a diversidade real:
**validação dirigida por config** + **helpers de extração reusáveis**. Scrapers complexos
(ConsigNet, Fasitec, ConsigLog, DigitalConsig) seguem como override — fora de escopo.

## Diagnóstico (da exploração)
Já é config-driven: auth, seletores de login, URL, parte da seleção de órgão. **`validate_access`
é bespoke em todo scraper mas é quase tudo "URL + seletores + keywords"** → declarável. A
**extração** é genuinamente diversa (regex/split/tabela/span/DOM) → helpers, NÃO DSL. **ConSIGI
e Konexia são idênticos** (mesmo PrimeFaces).

## Design
- **`app/scrapers/declarativo.py`** (puro o quanto der, opera sobre uma `page` Playwright):
  - `validar_acesso(page, regras, timeout)` — regras de config:
    `{sucesso_url: [...], sucesso_seletores: [...], falha_seletores: [...], falha_keywords: [...]}`.
    Ordem: **falha primeiro** (seletor/keyword visível → `CollectionError` com categoria —
    `credencial_expirada` se "xpirad", senão `auth_falhou`); depois **sucesso** (URL contém
    fragmento OU seletor presente → ok); senão **warning + ok** (não bloqueia).
  - Helpers de extração: `texto_por_label(page, label, sep=":")`, `regex_em_texto(page, seletor,
    padrao)`, `linhas_de_tabela(page, seletor)`.
- **`ScraperDeclarativo(BaseScraper)`** — implementa `validate_access()` lendo
  `processadora_config["validacao"]` e chamando `validar_acesso`. `collect()` continua abstrato
  (o scraper concreto usa os helpers em 1–3 linhas).
- **Config (`processadoras.json`):** bloco `validacao` por processadora.

## Migração (prova — os casos mais claros)
- **ConSIGI + Konexia** (idênticos) → `ScraperDeclarativo` + `texto_por_label`; remove a duplicação.
- **ConsigUp** → `ScraperDeclarativo` + `regex_em_texto`.
- (ProConsig, ConsigFacil = follow-up incremental.)

## Testes
- `validar_acesso`: falha (seletor/keyword → categoria certa), sucesso (URL/seletor), nada → ok.
- Helpers: `texto_por_label`, `regex_em_texto`, `linhas_de_tabela` com `page` mockada.
- Scrapers migrados: `validate_access`/`collect` com `page` mockada (padrão dos testes atuais).

## Fora de escopo
- DSL de extração 100%-config · navegação/auth complexa em config · migrar os 4 scrapers complexos.
