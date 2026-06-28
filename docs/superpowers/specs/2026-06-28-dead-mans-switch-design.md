# Spec — Dead-man's switch (Fase 2 / observabilidade)

Data: 2026-06-28 · Branch: feat/registro-falha-coleta · Status: design aprovado (run autônomo)

## Objetivo
"Quem vigia o vigia": se o ciclo de coleta **não rodar** (cron/runner caiu, DB fora, processo
morto), ninguém saberia. Um ping a um serviço de uptime externo ao fim de cada ciclo resolve —
a **ausência** do ping faz o serviço (ex.: healthchecks.io) alertar, INDEPENDENTE do monitor.

## Design
- **`app/services/healthcheck.py`**: `pingar(sucesso=True, url=None)` → `GET` ao
  `settings.HEALTHCHECK_URL` (sufixo `/fail` quando `sucesso=False`). **Best-effort**: timeout
  curto (8s), toda exceção engolida, no-op sem URL. Nunca afeta a coleta.
- **`settings.HEALTHCHECK_URL`** (env). Vazio = desabilitado.
- **Wiring (ambos os caminhos de "rodar tudo"):**
  - **Runner** (`run_daily_collection.main`, caminho de produção via cron): `pingar(sucesso=False)`
    antes de `return 1` (falhas inesperadas), `pingar(sucesso=True)` antes de `return 0`.
  - **Scheduler** (APScheduler in-API): como `executar_todas` **engole** falhas de coleta
    (não levanta), o sucesso é decidido pelos RESULTADOS — `sucesso = alguma processadora com
    status != erro` — senão o watchdog ficaria verde numa coleta 100% quebrada.
  - Um crash ANTES do ping (ex.: `db.assert_ready()`) → sem ping → o watchdog alerta. ✓

## Testes
- `pingar`: no-op sem URL, sucesso (2xx), sufixo `/fail`, erro de rede engolido, não-2xx.
- Scheduler: ping de sucesso quando alguma coleta; **`/fail` quando 100% erro** (não levanta);
  `/fail` na exceção.

## Follow-ups (menores, anotados)
- `/fail` por sufixo de path assume URL path-style (healthchecks.io); URL com query não casa.
- Branch de ping do runner `main()` não tem teste de unidade (lógica simples; semântica conferida).
