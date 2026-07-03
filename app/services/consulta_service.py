"""Montagem das linhas de corte atuais (a "verdade" que o painel e o sync consomem).

Extraído de app/api/main.py (refactor puro) para que o endpoint /cortes/atuais e o
sync do módulo de remessas usem EXATAMENTE a mesma montagem — mesma normalização,
mesma competência derivada, mesma confiança.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import EventoTipo
from app.core.loader import load_processadoras_config
from app.services.confianca import JANELA_DIAS, classificar_confianca, mudou_dia_corte
from app.services.orchestrator_factory import build_repositories
from app.utils.dates import derivar_competencia, normalizar_data_corte


def montar_dados_convenios() -> list[dict]:
    """Retorna dados de corte mais recentes de todos os convênios (sem filtros)."""
    config = load_processadoras_config()
    convenios_config = config["convenios"]

    execucao_repo, dados_repo, evento_repo = build_repositories()

    dados_por_convenio: dict[str, list] = {}
    mudancas_por_convenio: dict[str, int] = {}
    processadoras_carregadas: set[str] = set()

    for convenio_cfg in convenios_config.values():
        processadora_key = convenio_cfg["processadora"]
        if processadora_key in processadoras_carregadas:
            continue
        processadoras_carregadas.add(processadora_key)

        # Confiança: conta mudanças de data por convênio na janela (1 query/processadora).
        for e in evento_repo.listar(processadora_key, dias=JANELA_DIAS):
            if (e.tipo == EventoTipo.DATA_CORTE_ALTERADA.value
                    and mudou_dia_corte(e.data_corte_anterior, e.data_corte_nova)):
                mudancas_por_convenio[e.convenio_key] = mudancas_por_convenio.get(e.convenio_key, 0) + 1

        ultima = execucao_repo.buscar_ultima_ok(processadora_key)
        if not ultima:
            continue

        for d in dados_repo.buscar_por_execucao(ultima.id):
            dados_por_convenio.setdefault(d.convenio_key, []).append(d)

    resultado = []
    for convenio_key, convenio_cfg in convenios_config.items():
        proc_key = convenio_cfg["processadora"]
        nome = convenio_cfg.get("nome", convenio_key)
        dados = dados_por_convenio.get(convenio_key, [])
        offset = convenio_cfg.get("competencia_offset", 0)   # meses do corte → competência

        if not dados:
            default = convenio_cfg.get("data_corte_default")
            dc = normalizar_data_corte(default, None, datetime.now(timezone.utc).isoformat()) if default else None
            resultado.append({
                "convenio_key": convenio_key,
                "convenio_nome": nome,
                "processadora": proc_key,
                "folha": None,
                "mes_atual": None,
                "data_corte": dc,
                "coletado_em": None,
                "origem": None,
                "confianca": classificar_confianca(mudancas_por_convenio.get(convenio_key, 0)),
                "competencia": derivar_competencia(dc, offset),
            })
        else:
            for d in dados:
                dc = normalizar_data_corte(d.data_corte, d.mes_atual, d.coletado_em)
                resultado.append({
                    "convenio_key": convenio_key,
                    "convenio_nome": nome,
                    "processadora": proc_key,
                    "folha": d.folha,
                    "mes_atual": d.mes_atual,
                    "data_corte": dc,
                    "coletado_em": d.coletado_em,
                    "origem": d.origem,
                    "confianca": classificar_confianca(mudancas_por_convenio.get(convenio_key, 0)),
                    "competencia": derivar_competencia(dc, offset),
                })

    return resultado
