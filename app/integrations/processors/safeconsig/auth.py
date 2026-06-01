from __future__ import annotations

import logging

import requests

from app.integrations.processors.base.auth import ApiCredentials
from app.integrations.processors.base.exceptions import ApiError, AuthenticationError
from app.integrations.processors.base.utils import sanitize

logger = logging.getLogger(__name__)

_SAFE_RESPONSE_KEYS = ("usuarioValido", "situacaoRetorno", "mensagemRetorno")


class SafeConsigAuth:
    def autenticar(self, base_url: str, id_convenio: int, credentials: ApiCredentials) -> str:
        url = base_url.rstrip("/") + "/usuario/validar"

        payload = {
            "idConvenio": id_convenio,
            "usuario": credentials.username,
            "senha": credentials.password,
        }

        logger.info("[SafeConsig] POST %s", url)
        logger.info("[SafeConsig] payload: %s", sanitize(payload))

        try:
            response = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            raise ApiError(f"Falha de rede ao autenticar: {exc}") from exc

        logger.info("[SafeConsig] HTTP %s", response.status_code)

        try:
            data = response.json()
            safe = {k: data[k] for k in _SAFE_RESPONSE_KEYS if k in data}
            logger.info("[SafeConsig] resposta: %s", safe)
        except Exception:
            data = {}

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code
            if status == 401:
                mensagem = data.get("mensagemRetorno", "Credenciais inválidas")
                raise AuthenticationError(
                    f"[SafeConsig] Autenticação negada (HTTP 401): {mensagem}"
                ) from exc
            raise ApiError(
                f"HTTP {status} ao autenticar",
                status_code=status,
            ) from exc

        if not data.get("usuarioValido"):
            mensagem = data.get("mensagemRetorno", "usuarioValido=false")
            raise AuthenticationError(
                f"[SafeConsig] Autenticação negada (usuarioValido=false): {mensagem}"
            )

        logger.info("[SafeConsig] ✓ usuarioValido=True")

        token = data.get("authorization") or response.headers.get("Authorization", "")
        token = token.removeprefix("Bearer ").strip()

        if not token:
            raise AuthenticationError("[SafeConsig] Token não encontrado na resposta.")

        logger.info("[SafeConsig] token obtido com sucesso")
        return token
