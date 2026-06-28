"""Métricas de coleta — funções puras (a API injeta os dados dos repositórios).

- Taxa de sucesso por processadora (atual + média + tendência), do histórico de Execucao.
- Falhas por convênio (contagem de ERRO_COLETA na janela), dos eventos.
"""
from __future__ import annotations

from app.core.enums import EventoTipo

JANELA_DIAS = 30          # janela de eventos p/ falhas por convênio
LIMITE_EXECUCOES = 10     # execuções recentes consideradas na taxa por processadora
_ERRO = EventoTipo.ERRO_COLETA.value
# ERRO_COLETA é sobrecarregado: além de falhas reais carrega adiamento (fora_janela),
# gap (nao_executou), convênio já-conhecido-morto e sinais de qualidade do dado.
# "Falhas" lista só o ACIONÁVEL (auth/credencial/rede/timeout/portal/sem_dado/...).
_NAO_FALHA = {"fora_janela", "nao_executou", "falha_conhecida", "valor_invalido", "salto_suspeito"}


def _taxa(sucesso: int, total: int) -> float | None:
    return round(sucesso / total, 4) if total else None


def _considerados(e) -> int:
    """Convênios que contam pra taxa = ok + erros reais. EXCLUI fora_janela
    (success_count só conta 'ok'; error_count já exclui fora_janela)."""
    return e.success_count + e.error_count


def _tendencia(recentes: list) -> str:
    """Compara a taxa média da metade recente vs a metade antiga (precisa de >=4)."""
    if len(recentes) < 4:
        return "estavel"
    meio = len(recentes) // 2
    nova = _taxa(sum(e.success_count for e in recentes[:meio]),
                 sum(_considerados(e) for e in recentes[:meio]))
    velha = _taxa(sum(e.success_count for e in recentes[meio:]),
                  sum(_considerados(e) for e in recentes[meio:]))
    if nova is None or velha is None:
        return "estavel"
    if nova > velha + 0.05:
        return "melhorando"
    if nova < velha - 0.05:
        return "piorando"
    return "estavel"


def resumo_processadora(execucoes: list, limite: int = LIMITE_EXECUCOES) -> dict:
    """Taxa de sucesso das execuções (vêm DESC); usa as `limite` mais recentes.

    Execuções 100% fora_janela (considerados=0) são ignoradas — senão um run fora
    da janela (ex.: ConsigUp no fim de semana) baixaria a taxa pra 0% falsamente.
    """
    recentes = [e for e in execucoes if _considerados(e) > 0][:limite]
    if not recentes:
        return {"execucoes": 0, "ultima_em": None, "taxa_atual": None,
                "taxa_media": None, "tendencia": "sem_dados"}
    atual = recentes[0]
    return {
        "execucoes": len(recentes),
        "ultima_em": atual.executada_em,
        "taxa_atual": _taxa(atual.success_count, _considerados(atual)),
        "taxa_media": _taxa(sum(e.success_count for e in recentes),
                            sum(_considerados(e) for e in recentes)),
        "tendencia": _tendencia(recentes),
    }


def falhas_por_convenio(eventos: list) -> list[dict]:
    """Conta ERRO_COLETA por convênio (eventos já filtrados por janela), DESC por falhas.
    Mantém a categoria/subtipo do evento mais recente (eventos vêm do mais novo p/ o antigo)."""
    agg: dict[str, dict] = {}
    for e in eventos:
        if getattr(e.tipo, "value", e.tipo) != _ERRO:
            continue
        if (e.categoria or "") in _NAO_FALHA:  # adiamento/gap/conhecida/qualidade ≠ falha acionável
            continue
        a = agg.setdefault(e.convenio_key, {"convenio_key": e.convenio_key, "falhas": 0,
                                            "categoria": None, "subtipo": None})
        a["falhas"] += 1
        if a["categoria"] is None and e.categoria:
            a["categoria"] = e.categoria
        if a["subtipo"] is None and e.subtipo:
            a["subtipo"] = e.subtipo
    itens = list(agg.values())
    itens.sort(key=lambda x: x["falhas"], reverse=True)
    return itens
