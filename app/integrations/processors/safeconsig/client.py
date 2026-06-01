from __future__ import annotations

import logging

from app.integrations.processors.base.api_client import BaseApiClient
from app.integrations.processors.base.exceptions import ApiError
from app.integrations.processors.safeconsig.auth import SafeConsigAuth
from app.integrations.processors.safeconsig.config import SafeConsigConfig
from app.integrations.processors.safeconsig.schemas import MesPrimeiroDescontoResponse

logger = logging.getLogger(__name__)


class SafeConsigClient(BaseApiClient):
    def __init__(self, config: SafeConsigConfig) -> None:
        super().__init__(config)
        self.config: SafeConsigConfig = config

    def autenticar(self) -> str:
        auth = SafeConsigAuth()
        self._token = auth.autenticar(
            self.config.base_url,
            self.config.id_convenio,
            self.config.credentials,
        )
        return self._token

    def consultar_mes_primeiro_desconto(self, data_hora: str) -> MesPrimeiroDescontoResponse:
        """Consulta a competência prevista do primeiro desconto para uma data/hora.

        data_hora: formato "yyyy-MM-dd HH:mm" ou "yyyy-MM-dd HH:mm:ss"
        Retorna: {"competencia": "MM/YYYY"}

        Não representa data de corte oficial — use como indício de virada de competência.
        """
        if not self._token:
            raise RuntimeError("Cliente não autenticado. Chame autenticar() antes.")

        try:
            data = self._request(
                "GET",
                "/contrato/mesPrimeiroDesconto/consultar",
                headers={"Authorization": self._token},
                params={"dataHora": data_hora},
            )
        except ApiError as exc:
            if exc.status_code == 400:
                logger.debug("[SafeConsig] mesPrimeiroDesconto: 400 para dataHora=%r", data_hora)
                return {"competencia": None}
            raise

        competencia = data.get("competencia")
        logger.debug("[SafeConsig] mesPrimeiroDesconto: dataHora=%r → competencia=%r", data_hora, competencia)
        return {"competencia": competencia}
