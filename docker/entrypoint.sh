#!/usr/bin/env bash
# Entrypoint compartilhado:
#   1. importa o certificado de cliente (mTLS) do ConsigFácil no banco NSS, se
#      houver um arquivo em /run/secrets/consigfacil.p12;
#   2. quando STORAGE_BACKEND=postgres, aguarda o banco ficar disponível.
# As migrations são responsabilidade do serviço `migrate` (não aqui).
set -e

# ── Certificado de cliente (mTLS) para o ConsigFácil ──────────────────────────
# Equivale a ter o certificado instalado no repositório do Windows. A seleção
# automática para a URL é feita pela policy do Chrome (docker/chrome-policy.json).
CERT_FILE="${CONSIGFACIL_CERT_FILE:-/run/secrets/consigfacil.p12}"
NSSDB="$HOME/.pki/nssdb"
if [ -f "$CERT_FILE" ]; then
  echo "[entrypoint] Importando certificado de cliente (mTLS) no NSS db..."
  mkdir -p "$NSSDB"
  # IDEMPOTENTE: certutil -N em cima de um nssdb JÁ inicializado (restart do container)
  # entra em busy-loop e trava o boot pra sempre. Só inicializa se ainda não existe,
  # e TODA chamada NSS ganha timeout — o import nunca pode impedir a API de subir.
  if [ ! -f "$NSSDB/cert9.db" ]; then
    timeout 30 certutil -d "sql:$NSSDB" -N --empty-password 2>/dev/null \
      || echo "[entrypoint] AVISO: certutil -N falhou/expirou — seguindo sem import." >&2
  else
    echo "[entrypoint] NSS db já inicializado — pulando certutil -N."
  fi
  if [ -f "$NSSDB/cert9.db" ]; then
    if timeout 30 pk12util -d "sql:$NSSDB" -i "$CERT_FILE" -W "${CERT_PASSWORD:-}" >/tmp/pk12.out 2>&1; then
      echo "[entrypoint] Certificado importado com sucesso."
    else
      echo "[entrypoint] AVISO: falha/timeout ao importar o certificado — verifique CERT_PASSWORD e o arquivo." >&2
      sed 's/^/[pk12util] /' /tmp/pk12.out >&2 || true
    fi
  fi
else
  echo "[entrypoint] Nenhum certificado em $CERT_FILE — ConsigFácil (mTLS) não autenticará neste container."
fi

if [ "${STORAGE_BACKEND}" = "postgres" ]; then
  echo "[entrypoint] Aguardando PostgreSQL..."
  python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from app.core.settings import settings

for i in range(60):
    try:
        with create_engine(settings.DATABASE_URL).connect() as c:
            c.execute(text("SELECT 1"))
        print("[entrypoint] PostgreSQL disponível.")
        break
    except Exception as ex:
        print(f"[entrypoint] DB indisponível ({ex.__class__.__name__}), retry {i+1}/60...", flush=True)
        time.sleep(2)
else:
    print("[entrypoint] Timeout aguardando o PostgreSQL.", file=sys.stderr)
    sys.exit(1)
PY
fi

exec "$@"
