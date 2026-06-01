from __future__ import annotations

from typing import NotRequired, TypedDict


class ValidarUsuarioResponse(TypedDict):
    usuarioValido: bool
    mensagemRetorno: str
    authorization: NotRequired[str]


class MesPrimeiroDescontoRequest(TypedDict):
    dataHora: str  # formato: "yyyy-MM-dd HH:mm" ou "yyyy-MM-dd HH:mm:ss"


class MesPrimeiroDescontoResponse(TypedDict):
    competencia: str  # ex: "07/2025"
