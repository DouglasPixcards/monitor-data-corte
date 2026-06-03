"""Runner diário de coleta de datas de corte.

Executa todas as processadoras configuradas em sequência, com intervalo
entre elas e retry automático para as que falharem completamente. Delega
todo o trabalho real ao ColetaOrchestrator — não duplica lógica de
coleta, comparação, storage nem e-mail.

Uso:
    python scripts/run_daily_collection.py

Variáveis de ambiente:
    DAILY_COLLECTION_INTERVAL_MINUTES    Pausa entre processadoras (default: 5)
    DAILY_COLLECTION_MAX_RETRIES         Rounds de retry para falhas (default: 2)
    DAILY_COLLECTION_RETRY_DELAY_MINUTES Pausa antes de cada round de retry (default: 60)

Critério de retry:
    - status == "error" (todos os convênios falharam) → retenta
    - status == "ok" ou "partial_success" → considera bem-sucedido
    - Exceção inesperada no orchestrator → retenta
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_daily_collection")

from app.core.enums import CollectionStatus
from app.core.loader import load_processadoras_config
from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notification.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
)


# ── Configuração lida do ambiente ─────────────────────────────────────────────

def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        logger.warning("Variável %s inválida — usando default %d", key, default)
        return default


INTERVAL_MINUTES: int = _env_int("DAILY_COLLECTION_INTERVAL_MINUTES", 5)
MAX_RETRIES: int = _env_int("DAILY_COLLECTION_MAX_RETRIES", 2)
RETRY_DELAY_MINUTES: int = _env_int("DAILY_COLLECTION_RETRY_DELAY_MINUTES", 60)


# ── Orchestrator ──────────────────────────────────────────────────────────────

def _build_orchestrator() -> ColetaOrchestrator:
    return ColetaOrchestrator(
        execucao_repo=FileExecucaoRepository(settings.STORAGE_PATH),
        dados_repo=FileDadosCorteRepository(settings.STORAGE_PATH),
        evento_repo=FileEventoRepository(settings.STORAGE_PATH),
        comparador=ComparadorService(),
        notificador=EmailSMTPNotificador(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        ),
        destinatarios=settings.notification_DESTINATARIOS,
    )


# ── Rastreamento de resultado por processadora ────────────────────────────────

class _ResultadoProcessadora:
    def __init__(self, processadora: str) -> None:
        self.processadora = processadora
        self.status: str = "pendente"
        self.tentativas: int = 0
        self.erro: str | None = None

    @property
    def falhou(self) -> bool:
        return self.status in ("erro", "pendente")

    def registrar_sucesso(self, status_orchestrator: str) -> None:
        self.tentativas += 1
        self.status = "ok"
        self.erro = None
        if status_orchestrator == CollectionStatus.PARTIAL_SUCCESS:
            self.status = "partial_success"

    def registrar_erro(self, erro: str) -> None:
        self.tentativas += 1
        self.status = "erro"
        self.erro = erro

    def to_dict(self) -> dict:
        return {
            "processadora": self.processadora,
            "status": self.status,
            "tentativas": self.tentativas,
            "erro": self.erro,
        }


# ── Execução individual ───────────────────────────────────────────────────────

def _executar_processadora(
    orchestrator: ColetaOrchestrator,
    resultado: _ResultadoProcessadora,
) -> bool:
    """Chama orchestrator.executar() e registra o resultado. Retorna True se não falhou completamente."""
    tentativa = resultado.tentativas + 1
    logger.info(
        "[Runner] → %s (tentativa %d)", resultado.processadora, tentativa
    )
    try:
        execucao = orchestrator.executar(resultado.processadora)

        if execucao.status == CollectionStatus.ERROR:
            resultado.registrar_erro(
                f"Todos os convênios falharam — erros: "
                + ", ".join(
                    f"{e.get('convenio_key')}: {e.get('erro', '')}"
                    for e in (execucao.erros or [])
                )[:200]
            )
            logger.warning(
                "[Runner] ✗ %s — status=error (%d/%d convênios com falha)",
                resultado.processadora,
                execucao.error_count,
                execucao.total_convenios,
            )
            return False

        resultado.registrar_sucesso(execucao.status)
        logger.info(
            "[Runner] ✓ %s — status=%s sucesso=%d/%d",
            resultado.processadora,
            execucao.status,
            execucao.success_count,
            execucao.total_convenios,
        )
        return True

    except Exception as exc:
        resultado.registrar_erro(str(exc)[:300])
        logger.error("[Runner] ✗ %s — exceção: %s", resultado.processadora, exc)
        return False


# ── Rodada de execução (principal ou retry) ───────────────────────────────────

def _executar_rodada(
    orchestrator: ColetaOrchestrator,
    resultados: dict[str, _ResultadoProcessadora],
    processadoras: list[str],
    intervalo_segundos: int,
    label: str,
) -> list[str]:
    """Executa uma lista de processadoras com intervalo entre elas.

    Retorna as chaves das que falharam completamente (para eventual retry).
    """
    falhas: list[str] = []
    total = len(processadoras)

    logger.info("[Runner] ┌── %s (%d processadoras) ──", label, total)

    for i, processadora_key in enumerate(processadoras):
        sucesso = _executar_processadora(orchestrator, resultados[processadora_key])
        if not sucesso:
            falhas.append(processadora_key)

        if i < total - 1 and intervalo_segundos > 0:
            logger.info(
                "[Runner] │   aguardando %ds antes da próxima...", intervalo_segundos
            )
            time.sleep(intervalo_segundos)

    logger.info(
        "[Runner] └── %s concluída — ok: %d | falha: %d",
        label, total - len(falhas), len(falhas),
    )
    return falhas


# ── Resumo ────────────────────────────────────────────────────────────────────

def _salvar_resumo(
    inicio: datetime,
    fim: datetime,
    resultados: dict[str, _ResultadoProcessadora],
    retries_executados: int,
) -> Path:
    data_str = inicio.strftime("%Y-%m-%d")
    duracao = round((fim - inicio).total_seconds() / 60, 1)

    total = len(resultados)
    sucessos = sum(1 for r in resultados.values() if not r.falhou)
    falhas_persistentes = sum(1 for r in resultados.values() if r.falhou)

    resumo = {
        "data": data_str,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "duracao_minutos": duracao,
        "total_processadoras": total,
        "sucesso": sucessos,
        "falha_persistente": falhas_persistentes,
        "max_retries_configurado": MAX_RETRIES,
        "retries_executados": retries_executados,
        "intervalo_minutos": INTERVAL_MINUTES,
        "retry_delay_minutos": RETRY_DELAY_MINUTES,
        "processadoras": [r.to_dict() for r in resultados.values()],
    }

    runs_dir = Path(settings.STORAGE_PATH) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    caminho = runs_dir / f"{data_str}.json"
    caminho.write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return caminho


def _imprimir_resumo(
    resultados: dict[str, _ResultadoProcessadora],
    caminho: Path,
    inicio: datetime,
    fim: datetime,
) -> None:
    total = len(resultados)
    sucessos = sum(1 for r in resultados.values() if not r.falhou)
    falhas = total - sucessos
    duracao = round((fim - inicio).total_seconds() / 60, 1)

    print()
    print("=" * 65)
    print("  RESUMO DA COLETA DIÁRIA")
    print("=" * 65)
    print(f"  Início:  {inicio.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Fim:     {fim.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Duração: {duracao} min")
    print()
    print(f"  Total:         {total} processadoras")
    print(f"  Sucesso:       {sucessos}")
    print(f"  Falha persist: {falhas}")
    print()

    for r in resultados.values():
        icon = "✓" if not r.falhou else "✗"
        extra = f" (tentativas: {r.tentativas})" if r.tentativas > 1 else ""
        status_label = f"[{r.status}]" if r.status != "ok" else ""
        print(f"  {icon} {r.processadora:<22} {status_label}{extra}")
        if r.erro:
            print(f"      └ {r.erro[:90]}")

    print()
    print(f"  Resumo salvo em: {caminho}")
    print("=" * 65)
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    inicio = datetime.now(timezone.utc)

    config = load_processadoras_config()
    processadoras_keys = list(config["processadoras"].keys())

    logger.info(
        "[Runner] Iniciando coleta diária — %d processadoras | "
        "intervalo=%dmin | max_retries=%d | retry_delay=%dmin",
        len(processadoras_keys),
        INTERVAL_MINUTES,
        MAX_RETRIES,
        RETRY_DELAY_MINUTES,
    )

    orchestrator = _build_orchestrator()
    intervalo_segundos = INTERVAL_MINUTES * 60
    resultados = {key: _ResultadoProcessadora(key) for key in processadoras_keys}

    # Rodada principal
    falhas = _executar_rodada(
        orchestrator,
        resultados,
        processadoras_keys,
        intervalo_segundos,
        "Rodada principal",
    )

    # Rounds de retry para processadoras que falharam completamente
    retries_executados = 0
    for retry_num in range(1, MAX_RETRIES + 1):
        if not falhas:
            break

        logger.info(
            "[Runner] %d falha(s) — aguardando %dmin antes do retry %d/%d...",
            len(falhas),
            RETRY_DELAY_MINUTES,
            retry_num,
            MAX_RETRIES,
        )
        time.sleep(RETRY_DELAY_MINUTES * 60)

        falhas = _executar_rodada(
            orchestrator,
            resultados,
            falhas,
            intervalo_segundos,
            f"Retry {retry_num}/{MAX_RETRIES}",
        )
        retries_executados += 1

    fim = datetime.now(timezone.utc)
    caminho = _salvar_resumo(inicio, fim, resultados, retries_executados)
    _imprimir_resumo(resultados, caminho, inicio, fim)

    if falhas:
        logger.warning(
            "[Runner] Coleta concluída com %d falha(s) persistente(s): %s",
            len(falhas),
            falhas,
        )
        return 1

    logger.info("[Runner] Coleta diária concluída com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
