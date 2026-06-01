# SafeConsig — Integração via API REST

## Visão geral

A SafeConsig expõe uma API REST documentada em:
```
{BASE_URL}/swagger.json
```

A autenticação usa Bearer token com validade de 10 minutos, renovado automaticamente a cada chamada.

---

## Data de corte vs. Competência de primeiro desconto

| Conceito | Definição | Fonte confiável |
|---|---|---|
| **Data de corte** | Dia do mês até o qual contratos podem ser averbados para desconto na folha daquele mês | Portal/processadora (configuração da folha) |
| **Competência de primeiro desconto** | Mês/ano em que o primeiro desconto de um contrato seria realizado se averbado numa data hipotética | Endpoint `/contrato/mesPrimeiroDesconto/consultar` |

**O endpoint não retorna data de corte.** Ele responde à pergunta:
> "Se eu averbar um contrato agora (`dataHora`), em qual competência sairá o primeiro desconto?"

A **virada de competência** — quando a resposta muda de, por exemplo, `06/2025` para `07/2025` — pode ser usada como *indício* do corte, mas **não é uma confirmação**. A confirmação deve vir do portal ou da processadora antes de ser tratada como regra de negócio.

---

## Endpoint: `/contrato/mesPrimeiroDesconto/consultar`

**Método:** `GET`

**Header obrigatório:**
```
Authorization: <token>
```

**Query parameter obrigatório:**

| Parâmetro | Tipo | Formato | Exemplo |
|---|---|---|---|
| `dataHora` | string | `yyyy-MM-dd HH:mm` ou `yyyy-MM-dd HH:mm:ss` | `2025-06-07 23:30` |

**Resposta 200:**
```json
{
  "competencia": "07/2025"
}
```

**Resposta 400:**
```
Data inválida ou nenhum desconto encontrado
```

---

## Exemplo de saída sanitizada (script exploratório)

```
Período:  2025-06-01 → 2025-06-30
Horário:  10:00:00
Endpoint: /contrato/mesPrimeiroDesconto/consultar

DATA          COMPETENCIA   OBSERVAÇÃO
---------------------------------------------
2025-06-01    06/2025
2025-06-02    06/2025
...
2025-06-07    06/2025
2025-06-08    07/2025       *** VIRADA: 06/2025 → 07/2025
2025-06-09    07/2025
...

── Possíveis viradas de competência (virada_competencia) ────────────
  2025-06-08  06/2025 → 07/2025

ATENÇÃO: virada de competência ≠ data de corte oficial.
         Confirme com o portal antes de usar como regra de negócio.
```

O campo `authorization` (token JWT) nunca aparece nos logs nem na saída do terminal.

---

## Como executar

### Pré-requisitos

Configure no `.env`:
```
SAFECONSIG_HML_BASE_URL=https://modelo.safeconsig.com.br/ws/rest
SAFECONSIG_HML_ID_CONVENIO=<id>
SAFECONSIG_HML_USERNAME=<usuario>
SAFECONSIG_HML_PASSWORD=<senha>
```

### Teste de autenticação (Fase 1)
```bash
python scripts/test_safeconsig_auth.py
```

Saída esperada:
```
✓ Autenticação SafeConsig HML bem-sucedida.
```

### Mapa exploratório de competências (Fase 2)
```bash
# Mês corrente, horário 10:00:00
python scripts/test_safeconsig_mapa_competencias.py

# Período e horário customizados
python scripts/test_safeconsig_mapa_competencias.py 2025-06-01 2025-06-30 23:30:00
```

---

## Regras de segurança

- Token JWT nunca é logado, nem parcialmente.
- Senha nunca é logada.
- Credenciais lidas exclusivamente do `.env` — nunca hardcoded.
- Respostas que contêm `authorization` são sanitizadas antes de qualquer log.

---

## Próximas fases (não implementadas)

- **Fase 3:** integrar resultado de `consultar_mes_primeiro_desconto` com `/coletas` para persistir a competência estimada por convênio.
- **Fase 4:** rotina diária automatizada para atualizar o mapa de competências.
