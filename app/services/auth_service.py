"""Autenticação do módulo de remessas — usuários (bcrypt) + sessões server-side.

Sessão = token opaco (secrets.token_urlsafe) entregue num cookie HttpOnly; no banco só
vive o sha256 do token (vazamento do banco ≠ roubo de sessão). Revogação instantânea:
desativar usuário / logout marca `revogada_em`.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.storage.db import session_scope
from app.storage.remessas_models import SessaoRow, UsuarioRow

logger = logging.getLogger(__name__)

ROLES = ("admin", "operacoes", "conciliacao")

# Throttle de login em memória: após _MAX_FALHAS falhas seguidas, bloqueia por _BLOQUEIO_S.
_MAX_FALHAS = 5
_BLOQUEIO_S = 60
_falhas: dict[str, list] = {}  # username -> [contagem, bloqueado_ate_epoch]


# ── Senha ─────────────────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    # bcrypt trunca em 72 bytes — rejeita cedo em vez de truncar silenciosamente.
    if len(senha.encode("utf-8")) > 72:
        raise ValueError("Senha excede 72 bytes (limite do bcrypt).")
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ── Usuários ──────────────────────────────────────────────────────────────────

def criar_usuario(session: Session, username: str, display_name: str,
                  senha: str, role: str) -> UsuarioRow:
    """Cria um usuário (username normalizado p/ lowercase). Levanta ValueError em
    role inválida; o UNIQUE do banco barra duplicata (IntegrityError p/ o chamador)."""
    if role not in ROLES:
        raise ValueError(f"Role inválida: {role!r} (esperado: {', '.join(ROLES)})")
    usuario = UsuarioRow(
        id=str(uuid.uuid4()),
        username=username.strip().lower(),
        display_name=display_name.strip(),
        password_hash=hash_senha(senha),
        role=role,
        ativo=True,
    )
    session.add(usuario)
    return usuario


def buscar_por_username(session: Session, username: str) -> UsuarioRow | None:
    stmt = select(UsuarioRow).where(UsuarioRow.username == username.strip().lower())
    return session.execute(stmt).scalar_one_or_none()


# ── Login / sessões ───────────────────────────────────────────────────────────

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def autenticar(username: str, senha: str) -> UsuarioRow | None:
    """Valida credenciais (com throttle anti-brute-force). None = negado."""
    chave = username.strip().lower()
    agora = time.monotonic()

    contagem, bloqueado_ate = _falhas.get(chave, [0, 0.0])
    if agora < bloqueado_ate:
        logger.warning("[auth] login bloqueado por throttle: %s", chave)
        return None

    with session_scope() as session:
        usuario = buscar_por_username(session, chave)
        # verificação de senha SEMPRE roda (hash dummy quando usuário não existe)
        # para não vazar existência de username por timing.
        hash_alvo = usuario.password_hash if usuario else hash_senha("dummy-timing")
        senha_ok = verificar_senha(senha, hash_alvo)

        if usuario is None or not usuario.ativo or not senha_ok:
            contagem += 1
            bloqueio = agora + _BLOQUEIO_S if contagem >= _MAX_FALHAS else 0.0
            _falhas[chave] = [contagem, bloqueio]
            return None

    _falhas.pop(chave, None)
    return usuario


def criar_sessao(usuario_id: str) -> str:
    """Cria a sessão e devolve o TOKEN (vai pro cookie; nunca é armazenado)."""
    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_TTL_HORAS)
    with session_scope() as session:
        session.add(SessaoRow(token_hash=_token_hash(token),
                              usuario_id=usuario_id, expira_em=expira))
    return token


def validar_sessao(token: str | None) -> UsuarioRow | None:
    """Usuário da sessão, ou None (token ausente/inválido/expirado/revogado/inativo)."""
    if not token:
        return None
    try:
        th = _token_hash(token)
    except (UnicodeEncodeError, AttributeError):
        return None
    agora = datetime.now(timezone.utc)
    with session_scope() as session:
        row = session.execute(
            select(SessaoRow, UsuarioRow)
            .join(UsuarioRow, UsuarioRow.id == SessaoRow.usuario_id)
            .where(SessaoRow.token_hash == th)
        ).first()
        if row is None:
            return None
        sessao, usuario = row
        if sessao.revogada_em is not None or sessao.expira_em <= agora or not usuario.ativo:
            return None
        return usuario


def revogar_sessao(token: str | None) -> None:
    if not token:
        return
    agora = datetime.now(timezone.utc)
    with session_scope() as session:
        sessao = session.get(SessaoRow, _token_hash(token))
        if sessao is not None and sessao.revogada_em is None:
            sessao.revogada_em = agora


def revogar_sessoes_do_usuario(session: Session, usuario_id: str) -> None:
    """Revoga todas as sessões ativas do usuário (ex.: ao desativá-lo)."""
    agora = datetime.now(timezone.utc)
    for sessao in session.execute(
        select(SessaoRow).where(SessaoRow.usuario_id == usuario_id,
                                SessaoRow.revogada_em.is_(None))
    ).scalars():
        sessao.revogada_em = agora
