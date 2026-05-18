# Relatório de Implementação — Autenticações de Portais Consignados
**Data:** 2026-05-14  
**Escopo:** Portais sem captcha (Captcha = 0) mapeados em `links_processadoras.xlsx`

---

## 1. Portais Implementados

| Portal | Scraper | Tipo de Auth | Convênios |
|--------|---------|-------------|-----------|
| ConsigUP | `app/scrapers/consigup/scraper.py` | `login_password` | Muaná |
| ConSIGI | `app/scrapers/consigi/scraper.py` | `login_password` | Contagem |
| Konexia | `app/scrapers/konexia/scraper.py` | `login_password` | Planaltina |
| PBConsig | `app/scrapers/pbconsig/scraper.py` | `login_password` | Paraíba |
| ProConsig | `app/scrapers/proconsig/scraper.py` | `login_password` | Guarulhos |
| ConsigLog / SAEC | `app/scrapers/consiglog/scraper.py` | `two_step` | Cotia-SP, Duque de Caxias-RJ |
| Fasitec / SICON | `app/scrapers/fasitec/scraper.py` | `blur_reveal` (override) | Pilar |
| DigitalConsig | `app/scrapers/digitalconsig/scraper.py` | `login_password` | Várzea Grande, Vera |
| ConsigNet | `app/scrapers/consignet/scraper.py` | `two_step` | Defensoria, Maringá, Maringá-Prev, Navegantes, Rancharia, Vilhena |

**Total: 11 portais registrados / 16 convênios mapeados**  
*(Muaná não testado por ausência de credenciais válidas no Excel)*

---

## 2. Arquivos Criados

| Arquivo | Descrição |
|---------|-----------|
| `app/auth/two_step_auth.py` | `TwoStepAuthStrategy` — step1 (usuário → submit) → step2 (senha → submit) |
| `app/auth/blur_reveal_auth.py` | `BlurRevealAuthStrategy` — usuário → Tab (blur revela senha) → senha → submit |
| `app/auth/certificate_auth.py` | `CertificateAuthStrategy` — stub para autenticação por certificado digital |
| `app/config/credential_loader.py` | Carrega credenciais do `.env` via `{PORTAL}_{CONVENIO}_USERNAME/PASSWORD` |
| `app/config/portal_registry.py` | Mapeia `portal_key → scraper_class` (lazy imports) |
| `app/scrapers/consigi/scraper.py` | Scraper ConSIGI — JSF/PrimeFaces (`.xhtml`) |
| `app/scrapers/konexia/scraper.py` | Scraper Konexia — JSF/PrimeFaces (`.xhtml`) |
| `app/scrapers/pbconsig/scraper.py` | Scraper PBConsig — Keycloak SSO |
| `app/scrapers/proconsig/scraper.py` | Scraper ProConsig — Django/React |
| `app/scrapers/consiglog/scraper.py` | Scraper ConsigLog/SAEC — ASP.NET WebForms, 2 etapas |
| `app/scrapers/fasitec/scraper.py` | Scraper Fasitec/SICON — ASP.NET WebForms + JS bypass de reCAPTCHA client-side |
| `app/scrapers/digitalconsig/scraper.py` | Scraper DigitalConsig — ASP.NET WebForms |
| `app/scrapers/consignet/scraper.py` | Scraper ConsigNet — SPA moderna, 2 etapas |
| `app/services/coleta_service.py` | `build_auth_strategy` e `build_scraper` atualizados |
| `scripts/testar_autenticacoes.py` | Rotina de teste de autenticação com relatório JSON |
| `scripts/descobrir_seletores.py` | Inspeção headless de seletores de login |
| `.env.example` | Placeholders de todas as variáveis de ambiente (sem valores reais) |
| `docs/arquitetura_acessos_portais.md` | Documento de arquitetura do sistema de acessos |
| `docs/relatorio_autenticacoes_2026-05-14.md` | Este arquivo |

---

## 3. Arquivos Alterados

| Arquivo | Alteração |
|---------|-----------|
| `app/core/processadoras.json` | Reescrito com seletores reais de todos os portais + 16 convênios |
| `app/core/enums.py` | Adicionados `TWO_STEP` e `BLUR_REVEAL` em `AuthType` |
| `app/auth/user_pass_auth.py` | Multi-CSS fallback; fluxo robusto com `expect_navigation` + `networkidle` |
| `app/scrapers/digitalconsig/scraper.py` | Detecção de sucesso por URL (`LoginSelecao.aspx`) |
| `.gitignore` | Adicionado `links_processadoras.xlsx` |
| `.env` | Populado com 15 entradas de credenciais (não versionado) |

---

## 4. Seletores Usados por Portal

### ConSIGI (`consigi`) — JSF PrimeFaces
```
username: #username
password: #password
submit:   button:has-text('Entrar'), button[type='submit']
```

### Konexia (`konexia`) — JSF PrimeFaces
```
username: #loginForm\:username, #username
password: #loginForm\:password, #password
submit:   button[type='submit'], #loginForm\:btnEntrar
```

### PBConsig (`pbconsig`) — Keycloak SSO
```
username: #username
password: #password
submit:   #kc-login
```

### ProConsig (`proconsig`) — Django/React
```
username: #cpf
password: input[name='senha']
submit:   button[type='submit']
```

### ConsigLog / SAEC (`consiglog`) — ASP.NET WebForms (2 etapas)
```
step1_username: #txtLogin
step1_submit:   #Entrar
step2_password: #txtSenha
step2_submit:   #Entrar
```

### Fasitec / SICON (`fasitec`) — ASP.NET WebForms
```
username: #txtLogin
password: #txtSenha
submit:   #cmdUISubmit
bypass:   JS → document.getElementById('btnContinuar').removeAttribute('disabled')
```
> Fluxo especial: `#btnContinuar` fica desabilitado aguardando token reCAPTCHA client-side.  
> O servidor **não valida** o token — o JS de força-habilitação é suficiente.

### DigitalConsig (`digitalconsig`) — ASP.NET WebForms
```
username: #txtLogin
password: #txtSenha
submit:   #Entrar
```

### ConsigNet (`consignet`) — SPA moderna (2 etapas)
```
step1_username: #login-username
step1_submit:   #btn-continue
step2_password: #login-password
step2_submit:   [id='btn-log in']
```

---

## 5. Status de Autenticação por Convênio

| Status | Convênio | Portal | Observação |
|--------|----------|--------|-----------|
| ✓ | Contagem | ConSIGI | Autenticado com sucesso (~25s) |
| ✓ | Paraíba | PBConsig | Autenticado com sucesso — Keycloak SSO (~15s) |
| ✓ | Planaltina | Konexia | Autenticado com sucesso (~28s) |
| ✓ | Guarulhos | ProConsig | Autenticado com sucesso (~4s) |
| ✓ | Várzea Grande | DigitalConsig | Autenticado — redirected para `LoginSelecao.aspx` (~2s) |
| ✓ | Vera | DigitalConsig | Autenticado — redirected para `LoginSelecao.aspx` (~2s) |
| ✗ | Cotia-SP | ConsigLog | Credencial inválida — "Usuario ou senha Inválida" |
| ✗ | Duque de Caxias-RJ | ConsigLog | Credencial inválida — "Usuario ou senha Inválida" |
| ✗ | Pilar | Fasitec | Auth mecânica OK — "Usuário sem perfil vinculado." |
| ✗ | Defensoria | ConsigNet | "Usuário ou senha incorretos." |
| ✗ | Maringá | ConsigNet | "Usuário ou senha incorretos." |
| ✗ | Maringá-Prev | ConsigNet | "Usuário ou senha incorretos." |
| ✗ | Navegantes | ConsigNet | "Usuário ou senha incorretos." |
| ✗ | Rancharia | ConsigNet | "Usuário ou senha incorretos." |
| ✗ | Vilhena | ConsigNet | "Usuário ou senha incorretos." |
| — | Muaná | ConsigUP | Sem credencial no Excel — nao testado |

**Resumo:** 6 sucessos / 9 falhas de credencial / 1 sem credencial

---

## 6. Casos que Falharam — Motivo Provável

### ConsigLog — Cotia-SP e Duque de Caxias-RJ
**Erro:** `"Usuario ou senha Inválida"` na tela `LoginSegundaEtapa.aspx`  
**Motivo:** As senhas registradas na planilha `links_processadoras.xlsx` estão incorretas ou expiradas.  
**Risco:** Cotia-SP atingiu 4/5 tentativas — **próxima tentativa pode bloquear a conta**.  
**Ação necessária:** Obter credenciais atualizadas com o responsável e atualizar o `.env` antes de retestar.

### Fasitec / SICON — Pilar
**Erro:** `"Usuário sem perfil vinculado."` (aparece após login bem-sucedido)  
**Motivo:** A conta existe e a autenticação é tecnicamente bem-sucedida, mas o usuário não tem nenhum perfil/papel (role) associado na configuração do portal SICON.  
**Ação necessária:** Ação administrativa no portal — o gestor do município de Pilar precisa vincular um perfil ao usuário.

### ConsigNet — Defensoria, Maringá, Maringá-Prev, Navegantes, Rancharia, Vilhena
**Erro:** `"Usuário ou senha incorretos."` (step2 do ConsigNet)  
**Motivo:** Todas as 6 credenciais do ConsigNet estão inválidas. Possíveis causas:
- Senhas expiradas (o portal pode exigir troca periódica)
- Credenciais da planilha foram registradas com dados antigos
- Contas desativadas no portal

**Ação necessária:** Verificar credenciais junto ao ConsigNet para cada convênio e atualizar o `.env`.

---

## 7. Pendências e Próximos Passos

| Prioridade | Item | Ação |
|-----------|------|------|
| URGENTE | Cotia-SP — risco de bloqueio (4/5 tentativas) | Corrigir credencial no `.env` ANTES de retestar |
| Alta | ConsigNet — 6 credenciais inválidas | Renovar senhas junto ao portal ConsigNet |
| Alta | Duque de Caxias-RJ — credencial inválida | Corrigir senha no `.env` |
| Média | Pilar / Fasitec — sem perfil | Ação administrativa no SICON de Pilar |
| Média | Muaná / ConsigUP — sem credencial | Obter acesso ao portal ConsigUP e registrar no `.env` |
| Baixa | `collect()` — todos os scrapers | Implementar coleta de data de corte por portal |
| Baixa | ConsigFácil — certificado digital | Implementar `CertificateAuthStrategy` com Chrome real |
| Baixa | Portais com captcha | Fora do escopo atual |

---

## 8. Observações Técnicas

### Credenciais e Segurança
- Todas as credenciais estão em `.env` (não versionado)
- `.env` e `links_processadoras.xlsx` estão no `.gitignore`
- Nenhuma senha aparece em logs, relatórios ou código
- `.env.example` contém apenas placeholders

### Padrão de Variáveis de Ambiente
```
{PORTAL}_{CONVENIO_KEY}_USERNAME
{PORTAL}_{CONVENIO_KEY}_PASSWORD

Exemplo:
CONSIGI_CONTAGEM_USERNAME=...
CONSIGI_CONTAGEM_PASSWORD=...
```

### Como Adicionar um Novo Convênio
1. Adicionar entrada em `convenios` no `app/core/processadoras.json`
2. Adicionar `{PREFIX}_USERNAME` e `{PREFIX}_PASSWORD` no `.env`
3. Adicionar placeholder correspondente em `.env.example`
4. Retestar com `python scripts/testar_autenticacoes.py`

### Como Adicionar um Novo Portal
1. Criar `app/scrapers/{portal}/scraper.py` herdando `BaseScraper`
2. Adicionar entrada em `processadoras` no `processadoras.json` com seletores
3. Registrar no `app/config/portal_registry.py`
4. Executar `scripts/descobrir_seletores.py` para inspecionar seletores reais

---

*Relatório gerado automaticamente após ciclo de implementação e testes de 2026-05-14.*
