# Painel de Datas de Corte (mini front)

Painel estilo "aeroporto" que mostra a **data de corte atual de todos os convênios**.
Consome a API do Monitor (`GET /cortes/atuais`) ao vivo, com busca, filtro por
processadora e atualização automática. É uma solução **temporária** até o software
definitivo ficar pronto — os dados vêm da mesma tabela, então a migração é só apontar
o novo software para a fonte.

## Desenvolvimento

```bash
cd frontend
npm install
npm run dev          # abre em http://localhost:5173 (proxy de /cortes -> API :8000)
```
> Suba a API do Monitor em paralelo (`uvicorn app.api.main:app` ou via Docker) para
> que o proxy `/cortes/atuais` responda.

## Build (gera os arquivos estáticos)

```bash
cd frontend
npm run build        # gera frontend/dist/
```

A API do Monitor serve automaticamente `frontend/dist/` em **`/painel`** quando o
diretório existe (ver `app/api/main.py`). No Docker, o build é feito no próprio
`docker compose build` (estágio Node do `Dockerfile`).

## Acesso

- Local: `http://localhost:8000/painel`
- Docker: `http://localhost:8000/painel` (serviço `api`)

## Estrutura

- `src/App.jsx` — painel, busca, filtro e render das linhas
- `src/lib.js` — fetch da API, parsing de datas, destaque por proximidade, hook de polling
- `src/styles.css` — visual do painel (tema escuro, responsivo)
- `vite.config.js` — `base: '/painel/'` + proxy de dev
