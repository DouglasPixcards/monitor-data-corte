# Spec — Erro tipado (categoria explícita no resultado)

Data: 2026-06-26 · Branch: feat/registro-falha-coleta · Status: design aprovado

## Contexto

Hoje a causa do erro é **derivada por heurística de string**: `comparador_service`
chama `classificar_erro(erro_string)` para obter a `categoria` do `Evento`. Isso é frágil
(ex.: "Senha do usuário está expirada" e "senha inválida" caem no mesmo `auth_falhou`;
um `TimeoutError` esperando um seletor que sumiu vira `timeout` em vez de portal quebrado).

Objetivo (fundação): permitir que o **coletor declare a categoria explicitamente**
(`erro_categoria`) no resultado, e os consumidores **preferirem** esse valor, caindo no
`classificar_erro(string)` só como **fallback**. Migração **incremental** — a suíte fica
verde o tempo todo; nada quebra para scrapers ainda não migrados.

## Design

### 1. Exceção tipada — `app/core/exceptions.py`
`CollectionError` (já existe, sem uso) ganha `categoria`:
```python
class CollectionError(Exception):
    def __init__(self, mensagem: str, categoria: str | None = None) -> None:
        super().__init__(mensagem)
        self.categoria = categoria
```

### 2. `base_scraper.run()` propaga a categoria
No bloco de erro, capturar `CollectionError` **antes** do `Exception` genérico:
```python
except CollectionError as e:
    return {..., "status": "erro", "dados": [], "erro": str(e), "erro_categoria": e.categoria}
except Exception as e:
    return {..., "status": "erro", "dados": [], "erro": str(e), "erro_categoria": None}
```
O branch de sucesso também ganha `"erro_categoria": None` (contrato consistente).

### 3. Threading do `erro_categoria`
- `coleta_service.executar_coleta_lote`: `resultado_convenio` ganha
  `"erro_categoria": resultado.get("erro_categoria")`. O branch `CredentialNotFoundError`
  passa `"erro_categoria": "auth_falhou"` (causa conhecida, sem heurística).
- `safeconsig/collector.py`: nos `except`, derivar a categoria do **tipo** da exceção
  (`AuthenticationError → "auth_falhou"`, `ApiError → "rede"` se a msg indicar rede, senão
  `None` — cai no fallback `classificar_erro`) e devolver `erro_categoria` no dict.
- `orchestrator.coletar`: `status_atual[ck]` ganha `"erro_categoria": c.get("erro_categoria")`.

### 4. Consumidores preferem o tipado (fallback no classificador)
- `comparador_service._comparar_status`: `categoria = cur.get("erro_categoria") or classificar_erro(erro)`.
- `orchestrator._erros_tecnicos_retentaveis`: `categoria = c.get("erro_categoria") or classificar_erro(c.get("erro"))`; lógica de credencial/técnico inalterada.

`classificar_erro` **não muda** (continua como fallback). `Evento.categoria` continua string.

## Arquivos
| Arquivo | Mudança |
|---|---|
| `app/core/exceptions.py` | `CollectionError.categoria` |
| `app/scrapers/base_scraper.py` | `run()` captura `CollectionError` → `erro_categoria` |
| `app/services/coleta_service.py` | thread `erro_categoria`; `CredentialNotFoundError → auth_falhou` |
| `app/integrations/processors/safeconsig/collector.py` | categoria por tipo de exceção |
| `app/services/orchestrator.py` | `status_atual` carrega `erro_categoria`; retry o prefere |
| `app/services/comparador_service.py` | prefere `erro_categoria` |

## Testes (TDD, mock)
- `base_scraper.run()`: um fake scraper que levanta `CollectionError(categoria="auth_falhou")` →
  resultado tem `erro_categoria == "auth_falhou"`; um que levanta `RuntimeError` → `erro_categoria is None`.
- `comparador`: `status_atual` com `erro_categoria="portal_mudou"` mas `erro="qualquer"` →
  Evento `categoria == "portal_mudou"` (preferiu o tipado, ignorou a heurística). Sem `erro_categoria` → usa `classificar_erro`.
- `retry`: convênio com `erro_categoria="auth_falhou"` e `erro="Timeout..."` (que heurística diria técnico) → **não** re-coletado (preferiu o tipado credencial).
- `safeconsig/collector`: `AuthenticationError` → `erro_categoria="auth_falhou"`.
- Suíte existente segue verde (fallback cobre scrapers não migrados).

## Fora de escopo (vai pra Feature 3 — detecção)
- Novas categorias `credencial_expirada` / `portal_quebrado` e a migração dos scrapers para
  levantá-las nos pontos de validate/collect, + destaque acionável no e-mail.

## Decisões (aprovadas)
- Categoria explícita no resultado + `classificar_erro` como fallback (não dataclass rica).
- Migração incremental e compatível.
