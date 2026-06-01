from __future__ import annotations


class IntegrationError(Exception):
    """Base para todas as falhas de integração."""


class AuthenticationError(IntegrationError):
    """Credenciais inválidas ou usuarioValido=false."""


class ApiError(IntegrationError):
    """Falha HTTP 4xx/5xx na API remota."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(IntegrationError):
    """Variável de ambiente obrigatória ausente."""
