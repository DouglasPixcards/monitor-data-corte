from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from dataclasses import asdict

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.loader import load_processadoras_config
from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notification.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.services.scheduler import SchedulerService
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
)
from app.utils.dates import normalizar_data_corte

logger = logging.getLogger(__name__)

# logger.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.SMTP_HOST:
        logger.warning("SMTP_HOST não configurado — notificações por e-mail desabilitadas")
    scheduler = SchedulerService(
        horario=settings.COLETA_HORARIO,
        orchestrator_factory=_build_orchestrator,
    )
    scheduler.iniciar()
    yield
    scheduler.parar()


app = FastAPI(title="Pipeline Corte API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/notification/testar")
def testar_smtp() -> dict:
    """
    POST /notification/testar

    → 422  se SMTP_HOST não estiver configurado
    → 422  se NOTIFICACAO_DESTINATARIOS estiver vazio
    → 500  se a conexão SMTP falhar
    → 200  {"status": "ok", "destinatarios": ["..."]}
    """
    if not settings.SMTP_HOST:
        raise HTTPException(status_code=422, detail="SMTP_HOST não configurado.")
    if not settings.notification_DESTINATARIOS:
        raise HTTPException(status_code=422, detail="notification_DESTINATARIOS não configurado.")
    notificador = EmailSMTPNotificador(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        user=settings.SMTP_USER, 
        password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_USE_TLS,
    )
    try:
        notificador.enviar(
            assunto="[Teste] Monitor Datas de Corte — verificação de SMTP",
            destinatarios=settings.notification_DESTINATARIOS,
            corpo_html="<p>Configuração SMTP funcionando corretamente.</p>",
        )
    except Exception:
        logger.exception("Falha no teste de envio SMTP")
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail de teste.")
    return {"status": "ok", "destinatarios": settings.notification_DESTINATARIOS}


def _executar_uma_processadora(processadora: str) -> dict:
    execucao = _build_orchestrator().executar(processadora)
    return {
        "id": execucao.id,
        "processadora": execucao.processadora,
        "status": execucao.status,
        "executada_em": execucao.executada_em,
        "total_convenios": execucao.total_convenios,
        "success_count": execucao.success_count,
        "error_count": execucao.error_count,
    }


@app.post("/coletas/{processadora}/executar")
def executar_coleta(processadora: str):
    if processadora == "all":
        config = load_processadoras_config()
        processadoras_ativas = sorted({
            cfg["processadora"] for cfg in config["convenios"].values()
        })

        resultados: list[dict] = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(_executar_uma_processadora, proc_key): proc_key
                for proc_key in processadoras_ativas
            }
            for future in as_completed(futures):
                proc_key = futures[future]
                try:
                    resultados.append(future.result())
                except Exception as e:
                    logger.exception("Falha ao executar coleta para %s", proc_key)
                    resultados.append({"processadora": proc_key, "status": "erro", "erro": str(e)})

        return sorted(resultados, key=lambda r: r["processadora"])

    try:
        return _executar_uma_processadora(processadora)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("Falha ao executar coleta para %s", processadora)
        raise HTTPException(status_code=500, detail="Falha interna ao executar coleta.")


@app.get("/coletas/{processadora}/execucoes")
def listar_execucoes(processadora: str) -> list[dict]:
    repo = FileExecucaoRepository(settings.STORAGE_PATH)
    return [asdict(e) for e in repo.listar(processadora)]


@app.get("/convenios")
def listar_convenios(
    processadora: Optional[str] = Query(None, description="Filtrar por processadora"),
    sem_dados: bool = Query(False, description="Retornar apenas convênios sem dados coletados"),
) -> list[dict]:
    config = load_processadoras_config()
    convenios_config = config["convenios"]

    execucao_repo = FileExecucaoRepository(settings.STORAGE_PATH)
    dados_repo = FileDadosCorteRepository(settings.STORAGE_PATH)

    # Carrega os dados mais recentes de cada processadora (uma única vez por processadora)
    dados_por_convenio: dict[str, list] = {}
    processadoras_carregadas: set[str] = set()

    for convenio_cfg in convenios_config.values():
        processadora_key = convenio_cfg["processadora"]
        if processadora_key in processadoras_carregadas:
            continue
        processadoras_carregadas.add(processadora_key)

        ultima = execucao_repo.buscar_ultima_ok(processadora_key)
        if not ultima:
            continue

        for d in dados_repo.buscar_por_execucao(ultima.id):
            dados_por_convenio.setdefault(d.convenio_key, []).append(d)

    # Monta a tabela com todos os convênios, com ou sem dados
    resultado = []
    for convenio_key, convenio_cfg in convenios_config.items():
        processadora = convenio_cfg["processadora"]
        nome = convenio_cfg.get("nome", convenio_key)
        dados = dados_por_convenio.get(convenio_key, [])

        if not dados:
            resultado.append({
                "convenio_key": convenio_key,
                "convenio_nome": nome,
                "processadora": processadora,
                "folha": None,
                "mes_atual": None,
                "data_corte": None,
                "coletado_em": None,
            })
        else:
            for d in dados:
                resultado.append({
                    "convenio_key": convenio_key,
                    "convenio_nome": nome,
                    "processadora": processadora,
                    "folha": d.folha,
                    "mes_atual": d.mes_atual,
                    "data_corte": normalizar_data_corte(d.data_corte, d.mes_atual, d.coletado_em),
                    "coletado_em": d.coletado_em,
                })

    if processadora:
        resultado = [r for r in resultado if r["processadora"] == processadora]

    if sem_dados:
        resultado = [r for r in resultado if r["data_corte"] is None]

    return resultado


@app.get("/coletas/{processadora}/eventos")
def listar_eventos(
    processadora: str,
    dias: int = Query(30, ge=1, le=365, description="Janela de dias para buscar eventos"),
) -> list[dict]:
    repo = FileEventoRepository(settings.STORAGE_PATH)
    eventos = repo.listar(processadora, dias=dias)
    return [asdict(e) for e in eventos]


@app.get("/coletas/{processadora}/dados")
def obter_dados_atuais(processadora: str) -> list[dict]:
    execucao_repo = FileExecucaoRepository(settings.STORAGE_PATH)
    dados_repo = FileDadosCorteRepository(settings.STORAGE_PATH)
    ultima = execucao_repo.buscar_ultima_ok(processadora)
    if not ultima:
        return []
    resultado = []
    for d in dados_repo.buscar_por_execucao(ultima.id):
        d_dict = asdict(d)
        d_dict["data_corte"] = normalizar_data_corte(d.data_corte, d.mes_atual, d.coletado_em)
        resultado.append(d_dict)
    return resultado
