"""Matriz de permissão por campo + regras contextuais + auditoria + projeções."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services import remessas_service as svc
from app.storage.remessas_models import (
    CicloRemessaRow,
    ConvenioRegistroRow,
    RemessaAuditoriaRow,
    UsuarioRow,
)


def _user(role):
    return UsuarioRow(id=f"u-{role}", username=role, display_name=role.title(),
                      password_hash="h", role=role, ativo=True)


def _registro(monitor_key=None, tipo="remessa"):
    return ConvenioRegistroRow(id="r1", cod_empr=42, nome="Gov Teste",
                               tipo_desconto=tipo, monitor_key=monitor_key,
                               prod_credito=True, prod_beneficio=False,
                               prod_compras=False, ativo=True)


def _ciclo(**kw):
    base = dict(id="c1", registro_id="r1", competencia="07/2026",
                competencia_inicio=date(2026, 7, 1), data_site=date(2026, 7, 20),
                data_site_alterada=False, validado=False)
    base.update(kw)
    return CicloRemessaRow(**base)


def _sessao(ciclo, registro):
    session = MagicMock()
    session.get.side_effect = lambda model, _id: (
        ciclo if model is CicloRemessaRow else registro)
    session.auditorias = []
    session.add.side_effect = lambda obj: (
        session.auditorias.append(obj) if isinstance(obj, RemessaAuditoriaRow) else None)
    return session


# ── Matriz papel × campo ──────────────────────────────────────────────────────

@pytest.mark.parametrize("role,campo,valor,permitido", [
    ("conciliacao", "data_envio", date(2026, 7, 15), True),
    ("conciliacao", "valor_enviado", Decimal("100.00"), True),
    ("conciliacao", "validado", True, True),
    ("conciliacao", "corte_banksoft", date(2026, 7, 13), False),   # só operações/admin
    ("operacoes", "corte_banksoft", date(2026, 7, 13), True),
    ("operacoes", "data_envio", date(2026, 7, 15), False),
    ("operacoes", "valor_enviado", Decimal("1.00"), False),
    ("operacoes", "observacao", "x", False),
    ("admin", "corte_banksoft", date(2026, 7, 13), True),
    ("admin", "data_envio", date(2026, 7, 15), True),
])
def test_matriz_permissao_por_campo(role, campo, valor, permitido):
    ciclo, registro = _ciclo(), _registro()
    session = _sessao(ciclo, registro)
    if permitido:
        svc.atualizar_ciclo(session, "c1", {campo: valor}, _user(role))
        assert getattr(ciclo, campo) == valor
        assert len(session.auditorias) == 1
        assert session.auditorias[0].campo == campo
    else:
        with pytest.raises(svc.PermissaoNegada) as ei:
            svc.atualizar_ciclo(session, "c1", {campo: valor}, _user(role))
        assert campo in ei.value.campos
        assert getattr(ciclo, campo) != valor or valor is None


def test_rejeicao_total_sem_aplicacao_parcial():
    # 1 campo permitido + 1 negado → NADA é aplicado
    ciclo, registro = _ciclo(), _registro()
    session = _sessao(ciclo, registro)
    with pytest.raises(svc.PermissaoNegada):
        svc.atualizar_ciclo(session, "c1", {
            "data_envio": date(2026, 7, 15),      # conciliação pode
            "corte_banksoft": date(2026, 7, 13),  # conciliação NÃO pode
        }, _user("conciliacao"))
    assert ciclo.data_envio is None
    assert session.auditorias == []


# ── Regras contextuais ────────────────────────────────────────────────────────

def test_data_site_bloqueada_para_monitorado_mesmo_admin():
    ciclo, registro = _ciclo(), _registro(monitor_key="contagem")
    session = _sessao(ciclo, registro)
    with pytest.raises(svc.PermissaoNegada) as ei:
        svc.atualizar_ciclo(session, "c1", {"data_site": date(2026, 7, 21)}, _user("admin"))
    assert ei.value.campos == ["data_site"]


def test_data_site_manual_para_nao_monitorado_marca_origem():
    ciclo, registro = _ciclo(data_site=None), _registro(monitor_key=None)
    session = _sessao(ciclo, registro)
    svc.atualizar_ciclo(session, "c1", {"data_site": date(2026, 7, 21)}, _user("conciliacao"))
    assert ciclo.data_site == date(2026, 7, 21)
    assert ciclo.data_site_origem == "manual"
    assert ciclo.data_site_atualizada_em is not None


def test_ciente_so_aceita_false():
    ciclo, registro = _ciclo(data_site_alterada=True), _registro()
    session = _sessao(ciclo, registro)
    with pytest.raises(svc.PermissaoNegada):
        svc.atualizar_ciclo(session, "c1", {"data_site_alterada": True}, _user("conciliacao"))
    svc.atualizar_ciclo(session, "c1", {"data_site_alterada": False}, _user("conciliacao"))
    assert ciclo.data_site_alterada is False


def test_valor_igual_nao_gera_auditoria():
    ciclo, registro = _ciclo(validado=False), _registro()
    session = _sessao(ciclo, registro)
    svc.atualizar_ciclo(session, "c1", {"validado": False}, _user("conciliacao"))
    assert session.auditorias == []


def test_auditoria_registra_antes_e_depois():
    ciclo, registro = _ciclo(qtd_contratos=3), _registro()
    session = _sessao(ciclo, registro)
    svc.atualizar_ciclo(session, "c1", {"qtd_contratos": 5}, _user("conciliacao"))
    [a] = session.auditorias
    assert (a.valor_anterior, a.valor_novo) == ("3", "5")
    assert a.usuario_nome == "Conciliacao"


# ── Status / divergência / projeção ───────────────────────────────────────────

def test_status_derivado():
    assert svc.status_ciclo(_registro(tipo="automatico"), _ciclo()) == "automatico"
    assert svc.status_ciclo(_registro(), _ciclo(data_envio=None)) == "pendente"
    assert svc.status_ciclo(_registro(), _ciclo(data_envio=date(2026, 7, 1))) == "enviado"


def test_divergencia_valor_e_qtd():
    c = _ciclo(valor_enviado=Decimal("100.00"), credito_valor=Decimal("60.00"),
               beneficio_valor=Decimal("30.00"), qtd_contratos=5, credito_qtd=5)
    p = svc.proj_ciclo(c, _registro(), "conciliacao")
    assert p["divergencia"] == {"valor": True, "qtd": False}   # 60+30 != 100; 5 == 5


def test_sem_detalhamento_nao_diverge():
    c = _ciclo(valor_enviado=Decimal("100.00"))
    assert svc.proj_ciclo(c, _registro(), "admin")["divergencia"] == {"valor": False, "qtd": False}


def test_projecao_operacoes_nao_contem_campos_da_conciliacao():
    c = _ciclo(valor_enviado=Decimal("999.99"), data_envio=date(2026, 7, 1), observacao="secreta")
    p = svc.proj_ciclo(c, _registro(), "operacoes")
    for campo in ("valor_enviado", "data_envio", "observacao", "validado", "status", "divergencia"):
        assert campo not in p
    assert p["registro"] == {"cod_empr": 42, "nome": "Gov Teste"}


def test_sugestao_banksoft_menos_7_dias():
    p = svc.proj_ciclo(_ciclo(data_site=date(2026, 7, 20)), _registro(), "operacoes")
    assert p["sugestao_corte_banksoft"] == "2026-07-13"


def test_a_coletar_monitorado_sem_data():
    p = svc.proj_ciclo(_ciclo(data_site=None), _registro(monitor_key="contagem"), "operacoes")
    assert p["a_coletar"] is True
    p2 = svc.proj_ciclo(_ciclo(data_site=None), _registro(monitor_key=None), "operacoes")
    assert p2["a_coletar"] is False   # não-monitorado: é input manual, não "a coletar"


# ── Competência ───────────────────────────────────────────────────────────────

def test_parse_competencia():
    assert svc.parse_competencia("7/2026") == ("07/2026", date(2026, 7, 1))
    assert svc.parse_competencia("07-2026") == ("07/2026", date(2026, 7, 1))
    with pytest.raises(ValueError):
        svc.parse_competencia("13/2026")
    with pytest.raises(ValueError):
        svc.parse_competencia("julho")
