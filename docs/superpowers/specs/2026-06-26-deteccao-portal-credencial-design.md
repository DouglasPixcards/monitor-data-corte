# Spec — Detecção de portal quebrado / credencial expirada

Data: 2026-06-26 · Branch: feat/registro-falha-coleta · Status: design aprovado
Depende de: Feature 2 (erro tipado / `erro_categoria`).

## Contexto
Com o erro tipado (Feature 2), os scrapers podem declarar causas específicas. Dois modos
de falha de alto valor hoje ficam mascarados pela heurística de string:
- **Credencial expirada** (ex.: ConsigLog "Senha do usuário está expirada") cai em
  `auth_falhou`, indistinguível de senha errada — a ação é **renovar a senha**, não investigar login.
- **Portal quebrado** (seletor/elemento sumiu) frequentemente vira `timeout` (o
  `TimeoutError` do Playwright esperando o seletor) em vez de "portal mudou".

## Objetivo
Detectar e sinalizar esses dois modos com **categoria tipada** e **destaque acionável no e-mail**.

## Design
1. **Nova categoria `credencial_expirada`** em `CATEGORIAS` + `CATEGORIA_FRASE`
   ("credencial expirada — renovar a senha no portal").
2. **Retry:** `_erros_tecnicos_retentaveis` exclui `credencial_expirada` (determinístico, como
   `auth_falhou`) — re-coletar não muda nada antes da senha ser renovada.
3. **E-mail (destaque acionável):** `digest_builder` ganha um grupo `credencial_expirada`
   (extraído de `reais`) renderizado numa seção de **topo** "🔑 Credencial expirada — renovar a
   senha no portal", **sempre acionável** (entra em `_precisa_acao` → assunto `[Ação]`), mesmo
   se persistente (uma credencial expirada não-renovada continua sendo ação, não rodapé).
4. **Produtor (ConsigLog, o caso claro):** `consiglog/scraper.py`
   - `validate_access`: levanta `CollectionError(categoria="credencial_expirada")` quando a
     mensagem indica expiração ("xpirad"), senão `categoria="auth_falhou"` — em vez de `RuntimeError`.
   - `collect` (falha ao extrair a tabela após 3 tentativas): `CollectionError(categoria="portal_mudou")`.

## Arquivos
| Arquivo | Mudança |
|---|---|
| `app/services/erro_classifier.py` | categoria + frase `credencial_expirada` |
| `app/services/orchestrator.py` | retry exclui `credencial_expirada` |
| `app/services/notification/digest_builder.py` | grupo + seção de topo + `_precisa_acao` |
| `app/scrapers/consiglog/scraper.py` | `CollectionError` tipado em validate_access/collect |

## Testes (TDD, mock)
- ConsigLog: senha expirada → `CollectionError(categoria="credencial_expirada")`; login inválido
  → `categoria="auth_falhou"`.
- Digest: evento `credencial_expirada` → seção "Credencial expirada" + assunto `[Ação]`.
- Retry: `erro_categoria="credencial_expirada"` → não re-coletado (`call_count == 1`).

## Fora de escopo (migração incremental — decisão aprovada)
- Os demais scrapers (consigfacil, consigi, consignet, digitalconsig, fasitec, konexia,
  proconsig, consigup) adotam o `CollectionError` tipado nos seus pontos de validate/collect
  **incrementalmente**. Até lá, o fallback `classificar_erro(string)` continua cobrindo (sem regressão).
- Canal de alerta novo (Slack/webhook) — fica para a fase de observabilidade.
