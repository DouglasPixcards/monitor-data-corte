from __future__ import annotations

import uuid

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Evento
from app.services.storage_helpers import now_iso


class ComparadorService:
    def comparar(
        self,
        processadora: str,
        execucao_id: str,
        anteriores: list[DadoCorte],
        atuais: list[DadoCorte],
    ) -> list[Evento]:
        eventos: list[Evento] = []
        agora = now_iso()

        mapa_anterior = {self._chave(d): d for d in anteriores}
        mapa_atual = {self._chave(d): d for d in atuais}

        for chave, atual in mapa_atual.items():
            if chave not in mapa_anterior:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.REGISTRO_NOVO,
                    processadora=processadora,
                    convenio_key=atual.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=atual.folha,
                    mes_atual=atual.mes_atual,
                    data_corte_anterior=None,
                    data_corte_nova=atual.data_corte,
                ))
            elif mapa_anterior[chave].data_corte != atual.data_corte:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.DATA_CORTE_ALTERADA,
                    processadora=processadora,
                    convenio_key=atual.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=atual.folha,
                    mes_atual=atual.mes_atual,
                    data_corte_anterior=mapa_anterior[chave].data_corte,
                    data_corte_nova=atual.data_corte,
                ))

        for chave, anterior in mapa_anterior.items():
            if chave not in mapa_atual:
                eventos.append(Evento(
                    id=str(uuid.uuid4()),
                    tipo=EventoTipo.REGISTRO_NAO_ENCONTRADO,
                    processadora=processadora,
                    convenio_key=anterior.convenio_key,
                    execucao_id=execucao_id,
                    detectado_em=agora,
                    folha=anterior.folha,
                    mes_atual=anterior.mes_atual,
                    data_corte_anterior=anterior.data_corte,
                    data_corte_nova=None,
                ))

        return eventos

    @staticmethod
    def _chave(dado: DadoCorte) -> str:
        return f"{dado.convenio_key}|{(dado.folha or '').strip()}|{(dado.mes_atual or '').strip()}"
