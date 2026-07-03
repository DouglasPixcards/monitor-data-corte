"""Rotas do módulo de remessas — o router só traduz HTTP; as regras vivem no service.

PATCH parcial: campos AUSENTES não são tocados (exclude_unset); enviar null limpa.
Permissão por campo é validada no service (rejeição total, 403 com campos_negados).
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.api.deps import require_roles, usuario_atual
from app.services import remessas_service as svc
from app.storage.db import session_scope
from app.storage.remessas_models import UsuarioRow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remessas", tags=["remessas"])


# ── Registro (cadastro) ───────────────────────────────────────────────────────

class CriarRegistroBody(BaseModel):
    cod_empr: int = Field(ge=0)
    nome: str = Field(min_length=1, max_length=200)
    link_portal: str | None = Field(default=None, max_length=500)
    tipo_desconto: str
    prod_credito: bool = False
    prod_beneficio: bool = False
    prod_compras: bool = False
    monitor_key: str | None = None


class AtualizarRegistroBody(BaseModel):
    cod_empr: int | None = Field(default=None, ge=0)
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    link_portal: str | None = Field(default=None, max_length=500)
    tipo_desconto: str | None = None
    prod_credito: bool | None = None
    prod_beneficio: bool | None = None
    prod_compras: bool | None = None
    monitor_key: str | None = None
    ativo: bool | None = None


@router.get("/registros")
def listar_registros(_u: UsuarioRow = Depends(usuario_atual)) -> list[dict]:
    from sqlalchemy import select

    from app.storage.remessas_models import ConvenioRegistroRow
    with session_scope() as session:
        registros = session.execute(
            select(ConvenioRegistroRow).order_by(ConvenioRegistroRow.nome)
        ).scalars().all()
        return [svc.proj_registro(r) for r in registros]


@router.post("/registros", status_code=201)
def criar_registro(body: CriarRegistroBody,
                   admin: UsuarioRow = Depends(require_roles("admin"))) -> dict:
    try:
        with session_scope() as session:
            registro = svc.criar_registro(session, body.model_dump(), admin)
            # Se a competência corrente já está aberta, o novo convênio entra nela na hora.
            svc.ensure_ciclos(session, svc.competencia_corrente(), usuario=admin)
            session.flush()
            return svc.proj_registro(registro)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=409,
                            detail="cod_empr ou monitor_key já cadastrado (UNIQUE).")


@router.patch("/registros/{registro_id}")
def atualizar_registro(registro_id: str, body: AtualizarRegistroBody,
                       admin: UsuarioRow = Depends(require_roles("admin"))) -> dict:
    try:
        with session_scope() as session:
            registro = svc.atualizar_registro(
                session, registro_id, body.model_dump(exclude_unset=True), admin)
            session.flush()
            return svc.proj_registro(registro)
    except svc.NaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=409,
                            detail="cod_empr ou monitor_key já cadastrado (UNIQUE).")


@router.get("/monitor-keys")
def monitor_keys(_admin: UsuarioRow = Depends(require_roles("admin"))) -> list[dict]:
    with session_scope() as session:
        return svc.monitor_keys_livres(session)


# ── Ciclos ────────────────────────────────────────────────────────────────────

class PatchCicloBody(BaseModel):
    data_envio: date | None = None
    valor_enviado: Decimal | None = Field(default=None, ge=0)
    qtd_contratos: int | None = Field(default=None, ge=0)
    credito_valor: Decimal | None = Field(default=None, ge=0)
    credito_qtd: int | None = Field(default=None, ge=0)
    beneficio_valor: Decimal | None = Field(default=None, ge=0)
    beneficio_qtd: int | None = Field(default=None, ge=0)
    compras_valor: Decimal | None = Field(default=None, ge=0)
    compras_qtd: int | None = Field(default=None, ge=0)
    observacao: str | None = Field(default=None, max_length=2000)
    validado: bool | None = None
    corte_banksoft: date | None = None
    data_site: date | None = None
    data_site_alterada: bool | None = None


@router.get("/ciclos")
def listar_ciclos(competencia: str | None = Query(default=None),
                  usuario: UsuarioRow = Depends(usuario_atual)) -> list[dict]:
    comp = competencia or svc.competencia_corrente()
    try:
        with session_scope() as session:
            # A competência CORRENTE auto-abre no 1º acesso (virada de mês sem admin).
            if svc.parse_competencia(comp)[0] == svc.competencia_corrente():
                svc.ensure_ciclos(session, comp, usuario=None)
            return svc.listar_ciclos(session, comp, usuario.role)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/ciclos/{ciclo_id}")
def atualizar_ciclo(ciclo_id: str, body: PatchCicloBody,
                    usuario: UsuarioRow = Depends(usuario_atual)) -> dict:
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail="PATCH vazio.")
    try:
        with session_scope() as session:
            ciclo, registro = svc.atualizar_ciclo(session, ciclo_id, payload, usuario)
            session.flush()
            return svc.proj_ciclo(ciclo, registro, usuario.role)
    except svc.NaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except svc.PermissaoNegada as e:
        raise HTTPException(status_code=403,
                            detail={"mensagem": str(e), "campos_negados": e.campos})


@router.get("/ciclos/{ciclo_id}/auditoria")
def auditoria_ciclo(ciclo_id: str,
                    _u: UsuarioRow = Depends(usuario_atual)) -> list[dict]:
    with session_scope() as session:
        return svc.listar_auditoria(session, "ciclo", ciclo_id)


# ── Competências ──────────────────────────────────────────────────────────────

@router.get("/competencias")
def listar_competencias(_u: UsuarioRow = Depends(usuario_atual)) -> list[dict]:
    with session_scope() as session:
        return svc.listar_competencias(session)


@router.post("/competencias/{competencia}/abrir")
def abrir_competencia(competencia: str,
                      admin: UsuarioRow = Depends(require_roles("admin"))) -> dict:
    try:
        with session_scope() as session:
            criados = svc.ensure_ciclos(session, competencia, usuario=admin)
            comp, _ = svc.parse_competencia(competencia)
        # Ciclos criados → puxa os valores do monitor de cara (fora da transação acima).
        from app.services.remessas_sync import sincronizar_data_site
        sync = sincronizar_data_site(comp)
        return {"competencia": comp, "ciclos_criados": criados, "sync": sync}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Sync monitor → ciclos ─────────────────────────────────────────────────────

@router.post("/sync")
def sync(competencia: str | None = Query(default=None),
         _u: UsuarioRow = Depends(require_roles("admin", "conciliacao"))) -> dict:
    from app.services.remessas_sync import sincronizar_data_site
    try:
        return sincronizar_data_site(competencia)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
