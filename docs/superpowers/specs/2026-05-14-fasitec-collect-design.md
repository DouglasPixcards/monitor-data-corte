# Design: FasitecScraper.collect() — Pilar

## Escopo
Implementar `collect()` no `FasitecScraper` para extrair a data de corte do portal SICON (sicon.grupofasitec.com.br) para o convênio Pilar/AL.

## Fluxo pós-autenticação
1. `authenticate()` completa → URL: `Login.aspx` com "Selecione o Órgão" visível
2. `validate_access()` confirma tela de seleção ✓
3. `collect()`:
   a. Clica em `a[id*='imgEntrarNome']` → navega para `Inicial/Inicial.aspx`
   b. Fecha modal de aviso (`button:has-text("Fechar")`) se presente
   c. Lê `#table_config` filtrada por "Dia de Corte" (2ª das 3 tabelas com esse id)
   d. Retorna `[{"data_corte": "15", "folha": None, "mes_atual": None}]`

## Estrutura da tabela
```
#table_config (2ª instância — contém "Dia de Corte")
  tbody[0] → tr → th: "Dia de Corte" | "Dia de Repasse" | "Limite Importação Arquivo"
  tbody[1] → tr → td: "15"           | "5"              | ...
```

XPath de referência: `//*[@id="table_config"]/tbody[1]/tr/th[1]` (header) e `tbody[2]/tr/td[1]` (valor).

## Resiliência
- Modal fechado via try/except (silencioso se ausente)
- Tabela lida mesmo com modal (renderizada por trás)
- 3 tentativas com 2s entre elas (padrão ConsigFácil)
- Filtragem por conteúdo (`has_text="Dia de Corte"`) — imune a reordenação das tabelas
