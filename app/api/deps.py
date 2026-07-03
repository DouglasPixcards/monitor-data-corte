"""Dependencies FastAPI do módulo de remessas (sessão, papéis, gate Postgres)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.core.settings import settings
from app.services import auth_service
from app.storage.remessas_models import UsuarioRow

_COOKIE_SESSAO = "sessao"
_METODOS_LEITURA = ("GET", "HEAD", "OPTIONS")


def remessas_habilitado() -> None:
    """503 quando o backend não é Postgres — o módulo de remessas exige transações."""
    if not settings.REMESSAS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Módulo de remessas requer STORAGE_BACKEND=postgres.",
        )


def usuario_atual(request: Request) -> UsuarioRow:
    """Usuário da sessão (cookie HttpOnly). 401 sem sessão válida.

    Defesa extra anti-CSRF: mutações exigem o header X-Requested-With (setado pelo
    helper fetch do painel) — um form cross-site não consegue enviá-lo.
    """
    remessas_habilitado()
    usuario = auth_service.validar_sessao(request.cookies.get(_COOKIE_SESSAO))
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sessão ausente, inválida ou expirada.")
    if request.method not in _METODOS_LEITURA:
        if request.headers.get("X-Requested-With") != "fetch":
            raise HTTPException(status_code=403, detail="Header X-Requested-With ausente.")
    return usuario


def require_roles(*roles: str):
    """Dependency: usuário autenticado E com um dos papéis. 403 caso contrário."""

    def _dep(usuario: UsuarioRow = Depends(usuario_atual)) -> UsuarioRow:
        if usuario.role not in roles:
            raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")
        return usuario

    return _dep
