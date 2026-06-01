from __future__ import annotations

_SENSITIVE_KEYS = frozenset({
    "authorization",
    "senha",
    "password",
    "token",
    "access_token",
    "refresh_token",
})


def sanitize(data: dict) -> dict:
    """Retorna cópia do dict com valores sensíveis substituídos por '***'."""
    return {
        k: "***" if k.lower() in _SENSITIVE_KEYS else v
        for k, v in data.items()
    }
