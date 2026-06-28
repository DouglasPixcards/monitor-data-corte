# Spec — Alerting operacional com severidade (Contínuo / observabilidade)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (run autônomo)

## Objetivo
Canal de alerta em **tempo real** (Slack/webhook) para o que **precisa de atenção AGORA** —
distinto do webhook de DADOS (mudança de data) e complementar ao e-mail diário.

## Design
- **`settings.ALERT_WEBHOOK_URL`** (ex.: Slack incoming webhook). Vazio = desabilitado.
- **`app/services/notification/alerting.py`**:
  - `severidade(categoria)` → `critico` (`auth_falhou`, `credencial_expirada`, `portal_mudou`)
    / `atencao` (`salto_suspeito`, `valor_invalido`) / `None` (resto — e-mail cobre).
    **`auth_falhou` é crítico** — é a categoria de falha de credencial MAIS comum (o
    `credencial_expirada` só sai num caminho estreito do ConsigLog).
  - `montar_texto(eventos)` → agrupa os acionáveis por severidade num texto Slack-mrkdwn
    (`{text}`), com escape de `&<>`. **Ignora `subtipo` persistente/conhecida/gap** pra não
    re-alertar o mesmo problema todo dia (anti-fadiga); só o que é novo. Cap de 10 por severidade.
  - `disparar(eventos, url=None)` → POST best-effort; no-op sem URL ou sem itens acionáveis.
- **Integração:** `orchestrator.notificar_agregado` (ponto comum runner+scheduler) dispara o
  alerta com os eventos achatados de TODAS as processadoras, **independente do e-mail**.

## Testes
- `severidade` (incl. **auth_falhou=critico**); `montar_texto` (none sem acionáveis, agrupa,
  **persistente não re-alerta**, falha_nova alerta); `disparar` (no-op, payload, erro engolido);
  **integração** `notificar_agregado` → `disparar` com eventos achatados.

## Follow-ups (menores)
- `valor_invalido` (subtipo None) ainda pode repetir diariamente se o garbage persistir.
- Payload `{text}` é Slack/Mattermost; Discord/Teams usam formato diferente (genérico depois).
- De-dup com estado entre rodadas (hoje a anti-fadiga é só por subtipo).
