"""SafeConsig API Collector — adapter V1.

Encapsula SafeConsigClient no contrato de resultado esperado pelo pipeline
de coleta (coleta_service / ColetaOrchestrator).

ADAPTER TEMPORÁRIO V1: este módulo existe para encaixar uma integração via
API REST num pipeline projetado originalmente para scrapers. Em V2, isso será
substituído por uma abstração genérica ApiCollector que qualquer processadora
API possa implementar sem precisar de adapter.

Notas semânticas:
  - O campo `data_corte` armazenado aqui é a `competencia` retornada pela API,
    NÃO uma data de corte oficial confirmada.
  - O campo `folha` é definido como "virada_competencia" para que camadas
    downstream (DigestBuilder, logs) possam identificar a origem e usar
    linguagem adequada ("estimativa de competência").
  - Nunca interpretar este valor como corte oficial sem validação com a
    processadora.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.integrations.processors.base.exceptions import IntegrationError
from app.integrations.processors.safeconsig.client import SafeConsigClient
from app.integrations.processors.safeconsig.config import SafeConsigConfig

logger = logging.getLogger(__name__)

_FOLHA_MARKER = "virada_competencia"


class SafeConsigApiCollector:
    """Coleta a estimativa de competência de primeiro desconto via SafeConsig API.

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
            }

        try:
            config = SafeConsigConfig.from_env(env_key)
            client = SafeConsigClient(config)
            client.autenticar()
        except IntegrationError as exc:
            logger.error("[SafeConsigCollector] Falha na autenticação (%s): %s", convenio_key, exc)
            return {"status": "erro", "dados": [], "erro": str(exc)}

        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            resultado = client.consultar_mes_primeiro_desconto(data_hora)
        except IntegrationError as exc:
            logger.error("[SafeConsigCollector] Falha ao consultar competência (%s): %s", convenio_key, exc)
            return {"status": "erro", "dados": [], "erro": str(exc)}

        competencia = resultado.get("competencia")
        if not competencia:
            return {
                "status": "erro",
                "dados": [],
                "erro": f"API não retornou competência para dataHora={data_hora!r}.",
            }

        logger.info(
            "[SafeConsigCollector] %s → estimativa_competencia=%r (dataHora=%s)",
            convenio_key, competencia, data_hora,
        )
        return {
            "status": "ok",
            "dados": [{
                "folha": _FOLHA_MARKER,
                "mes_atual": None,
                "data_corte": competencia,
            }],
            "erro": None,
        }
