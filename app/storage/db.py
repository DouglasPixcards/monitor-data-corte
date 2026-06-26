"""Engine e sessão SQLAlchemy para o backend PostgreSQL.

Lazy/singleton: a engine só é criada na primeira vez que um repositório
Postgres precisa dela. Mantém o backend `file` totalmente desacoplado — quem
nunca usa Postgres não paga o custo de criar a engine nem exige DATABASE_URL.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL não configurada — STORAGE_BACKEND=postgres exige DATABASE_URL "
                "(ex: postgresql+psycopg://user:senha@db:5432/monitor)."
            )
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional: commit no sucesso, rollback em exceção, sempre fecha."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
