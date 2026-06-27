"""SafeConsig API Collector — adapter V1.

Encapsula SafeConsigClient no contrato de resultado esperado pelo pipeline
de coleta (coleta_service / ColetaOrchestrator).

ADAPTER TEMPORÁRIO V1: este módulo existe para encaixar uma integração via
API REST num pipeline projetado originalmente para scrapers. Em V2, isso será
substituído por uma abstração genérica ApiCollector que qualquer processadora
API possa implementar sem precisar de adapter.

Notas semânticas:
  - `data_corte` armazena a data estimada de corte: um dia antes da virada de
    competência, no formato DD/MM/YYYY. Validado empiricamente contra o portal
    de São João dos Patos (virada em 21/06 → corte em 20/06).
  - A virada é localizada por busca binária nos últimos _HORIZONTE_DIAS dias
    (~6 chamadas HTTP), sem necessidade de varredura completa do mês.
  - Se a virada estiver além do horizonte, `data_corte` cai de volta para a
    string de competência (ex: "07/2026") como fallback seguro.
  - O campo `folha` = "virada_competencia" sinaliza para camadas downstream
    (DigestBuilder, logs) que a origem é API e a linguagem deve ser "estimativa".
  - Nunca interpretar este valor como corte oficial sem validação com a processadora.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.integrations.processors.base.exceptions import AuthenticationError, IntegrationError
from app.integrations.processors.safeconsig.client import SafeConsigClient
from app.integrations.processors.safeconsig.config import SafeConsigConfig

logger = logging.getLogger(__name__)

_FOLHA_MARKER = "virada_competencia"
_HORIZONTE_DIAS = 40  # janela de busca para a virada de competência


def _estimar_data_corte(client: SafeConsigClient, competencia_atual: str) -> str | None:
    """Localiza a data de corte estimada via busca binária.

    Encontra o primeiro dia em que a API passou a retornar `competencia_atual`
    (= dia da virada) e retorna o dia anterior (= último dia da competência
    anterior = estimativa de data de corte), no formato DD/MM/YYYY.

    Faz no máximo 1 + ceil(log2(_HORIZONTE_DIAS)) ≈ 7 chamadas HTTP.
    Retorna None se a virada estiver além do horizonte configurado.
    """
    hoje = date.today()
    low = hoje - timedelta(days=_HORIZONTE_DIAS)
    high = hoje

    # Verifica se a competência já era a atual no início do horizonte
    r_low = client.consultar_mes_primeiro_desconto(f"{low} 10:00:00")
    if r_low.get("competencia") == competencia_atual:
        logger.warning(
            "[SafeConsigCollector] Virada anterior ao horizonte de %d dias "
            "— usando competência como fallback",
            _HORIZONTE_DIAS,
        )
        return None

    # Busca binária: encontrar o primeiro dia com competencia_atual
    while (high - low).days > 1:
        mid = low + (high - low) // 2
        r_mid = client.consultar_mes_primeiro_desconto(f"{mid} 10:00:00")
        if r_mid.get("competencia") == competencia_atual:
            high = mid   # virada está em mid ou antes
        else:
            low = mid    # virada está depois de mid

    # high = primeiro dia com competencia_atual (dia da virada)
    # data_corte estimada = dia anterior à virada
    data_corte = high - timedelta(days=1)
    logger.info(
        "[SafeConsigCollector] Virada em %s → data_corte estimada: %s",
        high.strftime("%d/%m/%Y"),
        data_corte.strftime("%d/%m/%Y"),
    )
    return data_corte.strftime("%d/%m/%Y")


class SafeConsigApiCollector:
    """Coleta a estimativa de data de corte via SafeConsig API.

    Método run() retorna o mesmo formato de resultado que BaseScraper.run(),
    permitindo integração direta com coleta_service.executar_coleta_lote().
    """

    def run(self, convenio_key: str, convenio_config: dict[str, Any]) -> dict[str, Any]:
        env_key = convenio_config.get("credential_env_key")
        if not env_key:
            return {
                "status": "erro",
                "dados": [],
                "erro": f"Campo 'credential_env_key' ausente na config do convênio '{convenio_key}'.",
                "erro_categoria": None,
            }

        try:
            config = SafeConsigConfig.from_env(env_key)
            client = SafeConsigClient(config)
            client.autenticar()
        except AuthenticationError as exc:
            logger.error("[SafeConsigCollector] Falha de autenticação (%s): %s", convenio_key, exc)
            return {"status": "erro", "dados": [], "erro": str(exc), "erro_categoria": "auth_falhou"}
        except IntegrationError as exc:
            logger.error("[SafeConsigCollector] Falha (%s): %s", convenio_key, exc)
            cat = "rede" if "rede" in str(exc).lower() else None
            return {"status": "erro", "dados": [], "erro": str(exc), "erro_categoria": cat}

        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            resultado = client.consultar_mes_primeiro_desconto(data_hora)
        except AuthenticationError as exc:
            logger.error("[SafeConsigCollector] Falha de autenticação (%s): %s", convenio_key, exc)
            return {"status": "erro", "dados": [], "erro": str(exc), "erro_categoria": "auth_falhou"}
        except IntegrationError as exc:
            logger.error("[SafeConsigCollector] Falha (%s): %s", convenio_key, exc)
            cat = "rede" if "rede" in str(exc).lower() else None
            return {"status": "erro", "dados": [], "erro": str(exc), "erro_categoria": cat}

        competencia = resultado.get("competencia")
        if not competencia:
            return {
                "status": "erro",
                "dados": [],
                "erro": f"API não retornou competência para dataHora={data_hora!r}.",
                "erro_categoria": None,
            }

        # Estima a data de corte: um dia antes da virada de competência.
        # Fallback para a string de competência se a busca não encontrar a virada.
        try:
            data_corte = _estimar_data_corte(client, competencia) or competencia
        except IntegrationError as exc:
            logger.warning(
                "[SafeConsigCollector] Erro na busca da virada (%s): %s — usando competência como fallback",
                convenio_key, exc,
            )
            data_corte = competencia

        logger.info(
            "[SafeConsigCollector] %s → competencia=%r data_corte=%r",
            convenio_key, competencia, data_corte,
        )
        return {
            "status": "ok",
            "dados": [{
                "folha": _FOLHA_MARKER,
                "mes_atual": None,
                "data_corte": data_corte,
            }],
            "erro": None,
            "erro_categoria": None,
        }
