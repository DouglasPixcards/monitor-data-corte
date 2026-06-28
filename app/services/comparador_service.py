from __future__ import annotations

import logging
import uuid

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Evento
from app.services.erro_classifier import classificar_erro
from app.services.storage_helpers import now_iso
from app.utils.dates import salto_data_corte_suspeito, validar_data_corte

logger = logging.getLogger(__name__)


class ComparadorService:
    def comparar(
        self,
        processadora: str,
        execucao_id: str,
        anteriores: list[DadoCorte],
        atuais: list[DadoCorte],
        status_anterior: dict[str, str] | None = None,
        status_atual: dict[str, dict] | None = None,
    ) -> list[Evento]:
        """Gera eventos comparando a coleta de hoje com a anterior.

        Camada de DADOS (sempre): REGISTRO_NOVO / DATA_CORTE_ALTERADA /
        REGISTRO_NAO_ENCONTRADO, comparando ``anteriores`` (baseline de dados =
        última ok/partial) com ``atuais`` (coletas ok de hoje).

        Camada de STATUS (opcional, só quando ``status_anterior`` e
        ``status_atual`` são passados): ERRO_COLETA (subtipos falha_nova /
        persistente / gap / conhecida) e RECUPERADO, comparando o status por
        convênio de hoje com o da última execução real (qualquer status).

        - ``status_anterior``: ``{convenio_key: "coletado" | "falhou"}``.
          "coletado" = teve DadoCorte na execução anterior; "falhou" = estava
          em ``Execucao.erros``. Convênio ausente do dict = não existia antes.
        - ``status_atual``: ``{convenio_key: {status, erro, known_failure,
          records_count, convenio_nome}}``.
        """
        eventos: list[Evento] = []
        agora = now_iso()

        mapa_anterior = self._construir_mapa(anteriores)
        mapa_atual = self._construir_mapa(atuais)

        # Convênios que coletaram OK hoje — usado para NÃO duplicar
        # REGISTRO_NAO_ENCONTRADO com os eventos de status (falha/gap).
        ok_hoje: set[str] | None = None
        if status_atual is not None:
            ok_hoje = {k for k, v in status_atual.items() if v.get("status") == "ok"}

        # --- Camada de DADOS ---
        for chave, atual in mapa_atual.items():
            # Garbage no data_corte (scrape quebrado) NÃO vira mudança nem registro novo:
            # emite sinal de qualidade acionável, evitando o falso DATA_CORTE_ALTERADA.
            if atual.data_corte is not None and not validar_data_corte(atual.data_corte, atual.coletado_em):
                eventos.append(self._ev_status(
                    processadora, atual.convenio_key, execucao_id, agora,
                    tipo=EventoTipo.ERRO_COLETA, categoria="valor_invalido", subtipo=None,
                    detalhe=f"data_corte inválida coletada (folha={atual.folha!r}): {atual.data_corte!r}",
                ))
                continue
            if chave not in mapa_anterior:
                eventos.append(self._ev(
                    EventoTipo.REGISTRO_NOVO, processadora, atual.convenio_key, execucao_id, agora,
                    folha=atual.folha, mes_atual=atual.mes_atual, data_corte_nova=atual.data_corte,
                ))
            elif mapa_anterior[chave].data_corte != atual.data_corte:
                anterior_dc = mapa_anterior[chave].data_corte
                eventos.append(self._ev(
                    EventoTipo.DATA_CORTE_ALTERADA, processadora, atual.convenio_key, execucao_id, agora,
                    folha=atual.folha, mes_atual=atual.mes_atual,
                    data_corte_anterior=anterior_dc, data_corte_nova=atual.data_corte,
                ))
                # Reconciliação: salto grande na data → sinal "conferir" (não bloqueia a mudança).
                if salto_data_corte_suspeito(anterior_dc, atual.data_corte):
                    eventos.append(self._ev_status(
                        processadora, atual.convenio_key, execucao_id, agora,
                        tipo=EventoTipo.ERRO_COLETA, categoria="salto_suspeito", subtipo=None,
                        detalhe=f"salto grande de data_corte: {anterior_dc!r} → {atual.data_corte!r}",
                    ))

        for chave, anterior in mapa_anterior.items():
            if chave not in mapa_atual:
                # Se hoje o convênio NÃO coletou ok (falhou/ausente), o evento de
                # status cobre o caso — evita ruído de "registro sumiu".
                if ok_hoje is not None and anterior.convenio_key not in ok_hoje:
                    continue
                eventos.append(self._ev(
                    EventoTipo.REGISTRO_NAO_ENCONTRADO, processadora, anterior.convenio_key, execucao_id, agora,
                    folha=anterior.folha, mes_atual=anterior.mes_atual,
                    data_corte_anterior=anterior.data_corte,
                ))

        # --- Camada de STATUS ---
        if status_anterior is not None and status_atual is not None:
            eventos.extend(
                self._comparar_status(processadora, execucao_id, agora, status_anterior, status_atual)
            )

        return eventos

    def _comparar_status(
        self,
        processadora: str,
        execucao_id: str,
        agora: str,
        status_anterior: dict[str, str],
        status_atual: dict[str, dict],
    ) -> list[Evento]:
        eventos: list[Evento] = []
        for convenio_key in sorted(set(status_anterior) | set(status_atual)):
            prev = status_anterior.get(convenio_key)        # "coletado" | "falhou" | None
            cur = status_atual.get(convenio_key)             # dict | None

            # 1) Não atendido hoje, mas existia na execução anterior -> gap.
            if cur is None:
                if prev in ("coletado", "falhou", "sem_dado"):
                    eventos.append(self._ev_status(
                        processadora, convenio_key, execucao_id, agora,
                        tipo=EventoTipo.ERRO_COLETA, categoria="nao_executou", subtipo="gap",
                        detalhe="Convênio não foi coletado nesta rodada (tinha histórico na execução anterior).",
                    ))
                continue

            # 2) Coletou de verdade hoje (status efetivo "ok" = veio data de corte).
            st = cur.get("status")
            if st == "ok":
                if prev in ("falhou", "sem_dado"):
                    eventos.append(self._ev_status(
                        processadora, convenio_key, execucao_id, agora,
                        tipo=EventoTipo.RECUPERADO, categoria=None, subtipo=None,
                        detalhe="Voltou a coletar após falha/sem-dado na execução anterior.",
                    ))
                continue

            # Pulado por janela de acesso — pendência informativa (rodapé).
            if st == "fora_janela":
                eventos.append(self._ev_status(
                    processadora, convenio_key, execucao_id, agora,
                    tipo=EventoTipo.ERRO_COLETA, categoria="fora_janela",
                    subtipo="fora_janela", detalhe=cur.get("erro"),
                ))
                continue

            # 3) Falhou (erro) OU coletou sem data de corte (sem_dado) hoje.
            #    "não coletava antes" = prev em (falhou, sem_dado, None).
            era_problematico = prev in ("falhou", "sem_dado")
            erro = cur.get("erro")
            if cur.get("known_failure"):
                categoria, subtipo = "falha_conhecida", "conhecida"
            elif st == "sem_dado":
                categoria = "sem_dado"
                subtipo = "persistente" if era_problematico else "falha_nova"
                erro = erro or "Coleta concluiu sem retornar data de corte."
            else:
                categoria = cur.get("erro_categoria") or classificar_erro(erro)
                subtipo = "persistente" if era_problematico else "falha_nova"
            eventos.append(self._ev_status(
                processadora, convenio_key, execucao_id, agora,
                tipo=EventoTipo.ERRO_COLETA, categoria=categoria, subtipo=subtipo, detalhe=erro,
            ))

        return eventos

    # ------------------------------------------------------------------
    # Construtores de Evento
    # ------------------------------------------------------------------

    @staticmethod
    def _ev(tipo, processadora, convenio_key, execucao_id, agora, *,
            folha=None, mes_atual=None, data_corte_anterior=None, data_corte_nova=None) -> Evento:
        return Evento(
            id=str(uuid.uuid4()), tipo=tipo, processadora=processadora, convenio_key=convenio_key,
            execucao_id=execucao_id, detectado_em=agora, folha=folha, mes_atual=mes_atual,
            data_corte_anterior=data_corte_anterior, data_corte_nova=data_corte_nova,
        )

    @staticmethod
    def _ev_status(processadora, convenio_key, execucao_id, agora, *,
                   tipo, categoria, subtipo, detalhe) -> Evento:
        return Evento(
            id=str(uuid.uuid4()), tipo=tipo, processadora=processadora, convenio_key=convenio_key,
            execucao_id=execucao_id, detectado_em=agora,
            categoria=categoria, subtipo=subtipo, detalhe=detalhe,
        )

    # ------------------------------------------------------------------
    # Mapa de dados
    # ------------------------------------------------------------------

    @staticmethod
    def _construir_mapa(dados: list[DadoCorte]) -> dict[str, DadoCorte]:
        mapa: dict[str, DadoCorte] = {}
        for d in dados:
            chave = ComparadorService._chave(d)
            if chave in mapa:
                logger.warning("Chave duplicada ignorada: %s", chave)
            mapa[chave] = d
        return mapa

    @staticmethod
    def _chave(dado: DadoCorte) -> str:
        # convenio_key é um identificador programático — assume-se sem espaços extras
        return f"{dado.convenio_key or ''}|{(dado.folha or '').strip()}|{(dado.mes_atual or '').strip()}"
