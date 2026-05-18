# Arquitetura — Gestão de Acessos aos Portais

## Visão Geral

O objetivo é centralizar o controle de acesso a todos os portais de consignados, permitindo:
- múltiplos convênios num mesmo portal sem duplicar código;
- credenciais fora do código-fonte;
- extensão futura para novos tipos de autenticação (certificado, SSO, OTP);
- rastreamento de status de autenticação por convênio.

---Co

## Estrutura de Pastas

```
monitor-data-corte/
├── app/
│   ├── auth/                          # Estratégias de autenticação
│   │   ├── base_auth_strategy.py      # ABC
│   │   ├── user_pass_auth.py          # LoginPasswordAuthStrategy
│   │   ├── two_step_auth.py           # TwoStepAuthStrategy (consiglog, consignet)
│   │   ├── blur_reveal_auth.py        # BlurRevealAuthStrategy (fasitec)
│   │   └── certificate_auth.py        # CertificateAuthStrategy (consigfacil)
│   │
│   ├── config/                        # Configuração e infraestrutura
│   │   ├── credential_loader.py       # Carrega credenciais do .env
│   │   └── portal_registry.py        # Mapeia portal_key → scraper class
│   │
│   ├── core/
│   │   ├── processadoras.json         # Definição de portais + convênios
│   │   ├── settings.py                # Configurações globais (headless, timeout)
│   │   ├── enums.py                   # AuthType, CollectionStatus, EventoTipo
│   │   └── loader.py                  # Carrega processadoras.json
│   │
│   ├── scrapers/                      # Um scraper por portal
│   │   ├── base_scraper.py            # ABC com start/stop/run/authenticate
│   │   ├── consigfacil/scraper.py
│   │   ├── consigup/scraper.py
│   │   ├── consigi/scraper.py         # Contagem
│   │   ├── konexia/scraper.py         # Planaltina
│   │   ├── pbconsig/scraper.py        # Paraíba (Keycloak)
│   │   ├── proconsig/scraper.py       # Guarulhos
│   │   ├── consiglog/scraper.py       # Cotia-SP, Duque de Caxias-RJ
│   │   ├── fasitec/scraper.py         # Pilar
│   │   ├── digitalconsig/scraper.py   # Várzea Grande, Vera
│   │   └── consignet/scraper.py       # Defensoria, Maringá, etc.
│   │
│   └── services/
│       └── coleta_service.py          # build_auth_strategy + build_scraper
│
├── scripts/
│   ├── testar_autenticacoes.py        # Rotina de teste de auth
│   └── descobrir_seletores.py         # Inspeção de seletores de portais
│
├── .env                               # Credenciais reais (não versionado)
├── .env.example                       # Placeholders (versionado)
└── docs/
    └── arquitetura_acessos_portais.md  # Este arquivo
```

---

## Modelo de Configuração

### processadoras.json

Cada portal define:
- `auth_type`: tipo de autenticação (`login_password`, `two_step`, `blur_reveal`, `certificate`)
- `uses_chrome_channel`: se precisa do Chrome real
- `selectors`: mapa de seletores CSS/ARIA para campos de login

Cada convênio define:
- `nome`: nome amigável
- `processadora`: chave do portal no bloco processadoras
- `credential_env_key`: prefixo para buscar `{PREFIX}_USERNAME` e `{PREFIX}_PASSWORD` no `.env`
- `base_url`: URL de login (ou `url_template` + `slug` para ConsigFácil)

```json
{
  "processadoras": {
    "consignet": {
      "auth_type": "two_step",
      "selectors": {
        "step1_username": { "type": "css", "value": "#login-username" },
        "step1_submit":   { "type": "css", "value": "#btn-continue" },
        "step2_password": { "type": "css", "value": "#login-password" },
        "step2_submit":   { "type": "css", "value": "[id='btn-log in']" }
      }
    }
  },
  "convenios": {
    "maringa": {
      "nome": "Maringá",
      "processadora": "consignet",
      "credential_env_key": "CONSIGNET_MARINGA",
      "base_url": "https://www.www1.consignet.com.br/auth/login"
    }
  }
}
```

### .env (não versionado)

Convenção: `{PORTAL}_{CONVENIO_KEY}_USERNAME` / `{PORTAL}_{CONVENIO_KEY}_PASSWORD`

```env
CONSIGNET_MARINGA_USERNAME=usuario@empresa.com.br
CONSIGNET_MARINGA_PASSWORD=****
```

---

## Fluxo de Execução

```
scripts/testar_autenticacoes.py
  └── carrega processadoras.json
  └── para cada convênio:
       ├── credential_loader.load_credentials(portal, convenio_key)  → (user, pwd)
       ├── coleta_service.build_auth_strategy(processadora_config, convenio_config)
       │     → LoginPasswordAuthStrategy | TwoStepAuthStrategy | BlurRevealAuthStrategy
       ├── portal_registry.get_scraper_class(portal_key)
       │     → ConsigiScraper | ConsignetScraper | ...
       ├── scraper.start()          → inicia browser Playwright
       ├── scraper.authenticate()   → chama auth_strategy.authenticate()
       ├── scraper.validate_access() → verifica se saiu da tela de login
       └── scraper.stop()
```

---

## Tipos de Autenticação

| Tipo | Classe | Portais | Fluxo |
|------|--------|---------|-------|
| `certificate` | CertificateAuthStrategy | ConsigFácil | Navega com certificado digital no Chrome |
| `login_password` | LoginPasswordAuthStrategy | ConsigUp, ConSIGI, Konexia, PBConsig, ProConsig, DigitalConsig | Preenche user + senha + clica submit |
| `two_step` | TwoStepAuthStrategy | ConsigLog, ConsigNet | Step1: user → submit → Step2: senha → submit |
| `blur_reveal` | BlurRevealAuthStrategy | Fasitec | User → Tab (blur revela senha) → senha → submit |

---

## Múltiplos Convênios no Mesmo Portal

O mesmo portal (`consignet`) atende 6 convênios. O scraper é único, a configuração varia:

```
consignet/scraper.py → ConsignetScraper
  recebe: convenio_config → { credential_env_key: "CONSIGNET_MARINGA" }
  carrega: CONSIGNET_MARINGA_USERNAME + CONSIGNET_MARINGA_PASSWORD
  usa:     mesmos seletores do portal consignet
```

Adicionar um novo convênio no mesmo portal = adicionar entrada em `convenios` no JSON, sem tocar no scraper.

---

## Status de Autenticação

O script `scripts/testar_autenticacoes.py` gera:
- Saída no terminal com ✓ / ✗ por convênio
- Arquivo `data/auth_test_results.json` com JSON completo
- Nenhuma credencial aparece nos logs ou no relatório

---

## O Que Está Pronto Agora

- Infraestrutura completa (portal_registry, credential_loader)
- 8 portais novos + 3 existentes = 11 portais registrados
- 15 convênios sem captcha mapeados e testados
- Script de teste de autenticação com relatório JSON
- Script de descoberta de seletores

## O Que Está Preparado Para Depois

| Funcionalidade | Onde estender |
|---------------|---------------|
| Certificado digital (novos portais) | Nova CertificateAuthStrategy ou configurar no existente |
| SSO / OAuth | Nova SSOAuthStrategy com redirect_uri handling |
| Captcha manual | Nova ManualCaptchaAuthStrategy + webhook para operador |
| Coleta de data de corte | Implementar `collect()` em cada scraper |
| Alertas de falha de login | Adicionar notificação no testar_autenticacoes.py |
| 80+ portais | Só criar scraper + entrada no JSON + .env |

---

## Segurança

1. `.env` no `.gitignore` — credenciais nunca versionadas
2. `links_processadoras.xlsx` no `.gitignore`
3. `credential_loader.py` nunca loga valores de credenciais
4. Relatório JSON nunca inclui senhas
5. Logs mascarados: usuário aparece apenas como `d***@empresa.com`
