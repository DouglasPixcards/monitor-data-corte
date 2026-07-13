# ── Estágio 1: build do painel (mini front React/Vite) ──
FROM node:20-alpine AS painel
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Estágio 2: aplicação Python ──
# Imagem oficial Playwright (Python) — já traz os browsers e as libs de SO.
# A tag casa com playwright==1.59.0 do requirements.
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

WORKDIR /app

# Dependências primeiro (cache de camada)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chrome

# Ferramentas NSS (certutil/pk12util) para importar o certificado de cliente (mTLS)
# usado pelo ConsigFácil, e diretório de policies gerenciadas do Chrome.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnss3-tools \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/opt/chrome/policies/managed

# Código
COPY . .
# Painel já buildado no estágio 1 (servido pela API em /painel)
COPY --from=painel /fe/dist ./frontend/dist
# Policy de seleção automática de certificado (equivale ao registro do Windows).
RUN chmod +x docker/entrypoint.sh \
    && cp docker/chrome-policy.json /etc/opt/chrome/policies/managed/consigfacil.json

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=True

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "scripts/run_scheduler_service.py"]
