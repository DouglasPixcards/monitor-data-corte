# SafeConsig — Integração via API REST

## Visão geral

A SafeConsig expõe uma API REST documentada em:
```
{BASE_URL}/swagger.json
```

A autenticação usa Bearer token com validade de 10 minutos, renovado automaticamente a cada chamada.

---

## Perfis configurados

Cada perfil SafeConsig é identificado por um prefixo de variável de ambiente (`env-key`).
Adicionar um novo perfil não requer nenhuma alteração de código — basta configurar as
quatro variáveis no `.env`.

| Perfil (`env-key`) | Ambiente | Convênio | Status |
|---|---|---|---|
| `SAFECONSIG_HML` | Homologação | Modelo (HML) | Ativo |
| `SAFECONSIG_PROD_SAOJOAODOSPATOS` | Produção | São João dos Patos | Ativo |
| `SAFECONSIG_PROD_CEARA` | Produção | Ceará | Pendente credenciais |
| `SAFECONSIG_PROD_ITAQUAQUECETUBA` | Produção | Itaquaquecetuba | Pendente credenciais |
| `SAFECONSIG_PROD_SANTOS` | Produção | Santos | Pendente credenciais |
| `SAFECONSIG_PROD_URUOCA` | Produção | Uruoca | Pendente credenciais |

Os convênios futuros (Ceará, Itaquaquecetuba, Santos, Uruoca) serão habilitados quando
recebermos as respectivas credenciais, URLs e `id_convenio`. O `.env.example` já contém
a estrutura comentada para cada um.

### Variáveis por perfil

Para cada `ENV_KEY`, configure no `.env`:
```
{ENV_KEY}_BASE_URL=https://<host>.safeconsig.com.br/ws/rest
{ENV_KEY}_ID_CONVENIO=<inteiro>
{ENV_KEY}_USERNAME=<usuario>
{ENV_KEY}_PASSWORD=<senha>
```

---

## Data de corte vs. Competência de primeiro desconto

| Conceito | Definição | Fonte confiável |
|---|---|---|
| **Data de corte** | Dia do mês até o qual contratos podem ser averbados para desconto na folha daquele mês | Portal/processadora (configuração da folha) |
| **Competência de primeiro desconto** | Mês/ano em que o primeiro desconto de um contrato seria realizado se averbado numa data hipotética | Endpoint `/contrato/mesPrimeiroDesconto/consultar` |

**O endpoint não retorna data de corte.** Ele responde à pergunta:
> "Se eu averbar um contrato agora (`dataHora`), em qual competência sairá o primeiro desconto?"

A **virada de competência** — quando a resposta muda de, por exemplo, `06/2026` para `07/2026` — pode ser usada como *indício* do corte, mas **não é uma confirmação**. A confirmação deve vir do portal ou da processadora antes de ser tratada como regra de negócio.

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
| `dataHora` | string | `yyyy-MM-dd HH:mm` ou `yyyy-MM-dd HH:mm:ss` | `2026-06-07 23:30` |

**Resposta 200:**
```json
{
  "competencia": "07/2026"
}
```

**Resposta 400:**
```
Data inválida ou nenhum desconto encontrado
```

---

## Como executar os scripts

### Pré-requisitos

Configure no `.env` as variáveis do perfil desejado. Exemplo para HML:
```
SAFECONSIG_HML_BASE_URL=https://modelo.safeconsig.com.br/ws/rest
SAFECONSIG_HML_ID_CONVENIO=300
SAFECONSIG_HML_USERNAME=<usuario>
SAFECONSIG_HML_PASSWORD=<senha>
```

### Teste de autenticação

```bash
# Homologação (default)
python scripts/test_safeconsig_auth.py

# Homologação (explícito)
python scripts/test_safeconsig_auth.py --env-key SAFECONSIG_HML

# Produção — São João dos Patos
python scripts/test_safeconsig_auth.py --env-key SAFECONSIG_PROD_SAOJOAODOSPATOS
```

Saída esperada:
```
✓ Autenticação SafeConsig bem-sucedida. (perfil: SAFECONSIG_HML)
```

### Mapa exploratório de competências

```bash
# Mês corrente, HML (default)
python scripts/test_safeconsig_mapa_competencias.py

# Período e horário customizados, HML
python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_HML 2026-06-01 2026-06-30 23:30:00

# Produção — São João dos Patos
python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_PROD_SAOJOAODOSPATOS

# Produção — São João dos Patos, período específico
python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_PROD_SAOJOAODOSPATOS 2026-06-01 2026-06-30 10:00:00
```

### Exemplo de saída

```
Perfil:   SAFECONSIG_PROD_SAOJOAODOSPATOS
Período:  2026-06-01 → 2026-06-30
Horário:  10:00:00
Endpoint: /contrato/mesPrimeiroDesconto/consultar

DATA          COMPETENCIA   OBSERVAÇÃO
---------------------------------------------
2026-06-01    06/2026
...
2026-06-16    07/2026       *** VIRADA: 06/2026 → 07/2026
...

── Possíveis viradas de competência (virada_competencia) ────────────
  2026-06-16  06/2026 → 07/2026

ATENÇÃO: virada de competência ≠ data de corte oficial.
         Confirme com o portal antes de usar como regra de negócio.
```

O campo `authorization` (token JWT) nunca aparece nos logs nem na saída do terminal.

---

## Regras de segurança

- Token JWT nunca é logado, nem parcialmente.
- Senha nunca é logada.
- Credenciais lidas exclusivamente do `.env` — nunca hardcoded.
- Respostas com `authorization` são sanitizadas antes de qualquer log.
- `.env` não é versionado. Somente `.env.example` (com placeholders) é commitado.

---

## Próximas fases (não implementadas)

- **Fase 3:** integrar resultado de `consultar_mes_primeiro_desconto` com `/coletas` para persistir a competência estimada por convênio.
- **Fase 4:** rotina diária automatizada para atualizar o mapa de competências.
- **Novos perfis:** habilitar Ceará, Itaquaquecetuba, Santos e Uruoca ao recebermos as credenciais.
