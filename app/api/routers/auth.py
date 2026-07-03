"""Rotas de autenticação e gestão de usuários (módulo de remessas).

Login entrega um cookie HttpOnly de sessão; /auth/me é a chamada de boot do painel
(diz se o módulo está habilitado e quem é o usuário). Usuários: sem DELETE — só
desativação (as linhas de auditoria referenciam o usuário pra sempre).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import remessas_habilitado, require_roles, usuario_atual
from app.core.settings import settings
from app.services import auth_service
from app.storage.db import session_scope
from app.storage.remessas_models import UsuarioRow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = "sessao"


def _user_publico(u: UsuarioRow) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name,
            "role": u.role, "ativo": u.ativo}


# ── Sessão ────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    remessas_habilitado()
    usuario = auth_service.autenticar(body.username, body.password)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    token = auth_service.criar_sessao(usuario.id)
    response.set_cookie(
        _COOKIE, token,
        httponly=True, samesite="lax", secure=settings.COOKIE_SECURE,
        max_age=settings.SESSION_TTL_HORAS * 3600, path="/",
    )
    logger.info("[auth] login: %s (%s)", usuario.username, usuario.role)
    return {"user": _user_publico(usuario), "remessas_enabled": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    if settings.REMESSAS_ENABLED:
        auth_service.revogar_sessao(request.cookies.get(_COOKIE))
    response.delete_cookie(_COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me")
def me(request: Request) -> dict:
    """Boot do painel. Módulo desabilitado → 200 com user=null (painel segue aberto,
    modo monitor). Habilitado sem sessão → 401 (painel mostra o login)."""
    if not settings.REMESSAS_ENABLED:
        return {"user": None, "remessas_enabled": False}
    usuario = auth_service.validar_sessao(request.cookies.get(_COOKIE))
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sessão ausente, inválida ou expirada.")
    return {"user": _user_publico(usuario), "remessas_enabled": True}


# ── Usuários (admin) ──────────────────────────────────────────────────────────

class CriarUsuarioBody(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    role: str


class AtualizarUsuarioBody(BaseModel):
    display_name: str | None = None
    role: str | None = None
    ativo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


@router.get("/usuarios")
def listar_usuarios(_admin: UsuarioRow = Depends(require_roles("admin"))) -> list[dict]:
    with session_scope() as session:
        usuarios = session.execute(
            select(UsuarioRow).order_by(UsuarioRow.username)
        ).scalars().all()
        return [_user_publico(u) for u in usuarios]


@router.post("/usuarios", status_code=201)
def criar_usuario(body: CriarUsuarioBody,
                  _admin: UsuarioRow = Depends(require_roles("admin"))) -> dict:
    try:
        with session_scope() as session:
            usuario = auth_service.criar_usuario(
                session, body.username, body.display_name, body.password, body.role)
            session.flush()
            return _user_publico(usuario)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' já existe.")


@router.patch("/usuarios/{usuario_id}")
def atualizar_usuario(usuario_id: str, body: AtualizarUsuarioBody,
                      admin: UsuarioRow = Depends(require_roles("admin"))) -> dict:
    if body.role is not None and body.role not in auth_service.ROLES:
        raise HTTPException(status_code=422, detail=f"Role inválida: {body.role!r}")
    with session_scope() as session:
        usuario = session.get(UsuarioRow, usuario_id)
        if usuario is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if body.display_name is not None:
            usuario.display_name = body.display_name.strip()
        if body.role is not None:
            usuario.role = body.role
        if body.password is not None:
            usuario.password_hash = auth_service.hash_senha(body.password)
        if body.ativo is not None:
            usuario.ativo = body.ativo
            if not body.ativo:  # desativou → derruba as sessões na hora
                auth_service.revogar_sessoes_do_usuario(session, usuario.id)
        logger.info("[auth] usuário %s atualizado por %s", usuario.username, admin.username)
        return _user_publico(usuario)
