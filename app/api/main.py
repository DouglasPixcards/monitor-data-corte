from __future__ import annotations

import logging
import logging.config
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone

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
from app.core.models import DadoCorte, Execucao
from app.core.settings import settings
from app.services.notification.smtp import EmailSMTPNotificador
from app.services.orchestrator_factory import build_orchestrator, build_repositories
from app.services.scheduler import SchedulerService
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
        orchestrator_factory=build_orchestrator,
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


# ── Painel estático (mini front React/Vite) ───────────────────────────────────
# Servido em /painel quando o build existir (frontend/dist). Mesma origem da API,
# então o painel consome /cortes/atuais sem precisar de CORS nem configurar URL.
from pathlib import Path as _Path

from fastapi.staticfiles import StaticFiles

_PAINEL_DIST = _Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _PAINEL_DIST.is_dir():
    app.mount("/painel", StaticFiles(directory=str(_PAINEL_DIST), html=True), name="painel")
    logger.info("Painel estático montado em /painel (%s)", _PAINEL_DIST)
else:
    logger.info("frontend/dist não encontrado — /painel desabilitado (rode 'npm run build').")


@app.get("/health")
def health() -> dict:
    import os
    from pathlib import Path
    storage = Path(settings.STORAGE_PATH)
    return {
        "status": "ok",
        "storage_path_config": settings.STORAGE_PATH,
        "storage_path_absolute": str(storage.resolve()),
        "storage_path_exists": storage.exists(),
        "cwd": os.getcwd(),
    }


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


def _resolver_key(key: str, config: dict) -> tuple[str, str | None]:
    """Resolve {key} como processadora ou convênio.

    Returns: (processadora_key, convenio_filter_or_None)
    """
    if key in config["processadoras"]:
        return key, None
    if key in config["convenios"]:
        return config["convenios"][key]["processadora"], key
    raise HTTPException(status_code=404, detail=f"Processadora ou convênio '{key}' não encontrado.")


def _executar_uma_processadora(processadora: str, convenio_filter: str | None = None) -> dict:
    execucao = build_orchestrator().executar(processadora, convenio_filter=convenio_filter)
    return {
        "id": execucao.id,
        "processadora": execucao.processadora,
        "status": execucao.status,
        "executada_em": execucao.executada_em,
        "total_convenios": execucao.total_convenios,
        "success_count": execucao.success_count,
        "error_count": execucao.error_count,
    }


@app.post("/coletas/{key}/executar")
def executar_coleta(key: str):
    """Aceita processadora (ex: consigi) ou convênio (ex: contagem) como {key}."""
    if key == "all":
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

    config = load_processadoras_config()

    # Chave é uma processadora conhecida → comportamento original
    if key in config["processadoras"]:
        try:
            return _executar_uma_processadora(key)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            logger.exception("Falha ao executar coleta para %s", key)
            raise HTTPException(status_code=500, detail="Falha interna ao executar coleta.")

    # Chave é um convênio → resolve a processadora e filtra
    if key in config["convenios"]:
        processadora_key = config["convenios"][key]["processadora"]
        try:
            return _executar_uma_processadora(processadora_key, convenio_filter=key)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            logger.exception("Falha ao executar coleta para convênio %s", key)
            raise HTTPException(status_code=500, detail="Falha interna ao executar coleta.")

    raise HTTPException(status_code=404, detail=f"Processadora ou convênio '{key}' não encontrado.")


@app.get("/coletas/{key}/execucoes")
def listar_execucoes(key: str) -> list[dict]:
    config = load_processadoras_config()
    processadora_key, _ = _resolver_key(key, config)
    repo, _dados, _eventos = build_repositories()
    return [asdict(e) for e in repo.listar(processadora_key)]


def _montar_dados_convenios() -> list[dict]:
    """Retorna dados de corte mais recentes de todos os convênios (sem filtros)."""
    config = load_processadoras_config()
    convenios_config = config["convenios"]

    execucao_repo, dados_repo, _eventos = build_repositories()

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

    resultado = []
    for convenio_key, convenio_cfg in convenios_config.items():
        proc_key = convenio_cfg["processadora"]
        nome = convenio_cfg.get("nome", convenio_key)
        dados = dados_por_convenio.get(convenio_key, [])

        if not dados:
            default = convenio_cfg.get("data_corte_default")
            resultado.append({
                "convenio_key": convenio_key,
                "convenio_nome": nome,
                "processadora": proc_key,
                "folha": None,
                "mes_atual": None,
                "data_corte": normalizar_data_corte(default, None, datetime.now(timezone.utc).isoformat()) if default else None,
                "coletado_em": None,
            })
        else:
            for d in dados:
                resultado.append({
                    "convenio_key": convenio_key,
                    "convenio_nome": nome,
                    "processadora": proc_key,
                    "folha": d.folha,
                    "mes_atual": d.mes_atual,
                    "data_corte": normalizar_data_corte(d.data_corte, d.mes_atual, d.coletado_em),
                    "coletado_em": d.coletado_em,
                })

    return resultado


@app.get("/convenios")
def listar_convenios(
    processadora: Optional[str] = Query(None, description="Filtrar por processadora"),
    sem_dados: bool = Query(False, description="Retornar apenas convênios sem dados coletados"),
) -> list[dict]:
    resultado = _montar_dados_convenios()

    if processadora:
        resultado = [r for r in resultado if r["processadora"] == processadora]

    if sem_dados:
        resultado = [r for r in resultado if r["data_corte"] is None]

    return resultado


@app.get("/cortes/atuais")
def cortes_atuais() -> list[dict]:
    """Dados de corte mais recentes de todos os convênios, ordenados por nome."""
    resultado = _montar_dados_convenios()
    return sorted(resultado, key=lambda r: (r["convenio_nome"] or "").lower())


@app.post("/convenios/{key}/data_corte")
def atualizar_data_corte(key: str, body: dict) -> dict:
    """Registra manualmente a data de corte de um convênio sem scraper.

    Body: {"data_corte": "01/07/2026"}
    """
    config = load_processadoras_config()
    if key not in config["convenios"]:
        raise HTTPException(status_code=404, detail=f"Convênio '{key}' não encontrado.")

    data_corte = (body or {}).get("data_corte")
    if not data_corte:
        raise HTTPException(status_code=422, detail="Campo 'data_corte' obrigatório.")

    convenio_cfg = config["convenios"][key]
    processadora_key = convenio_cfg["processadora"]
    nome = convenio_cfg.get("nome", key)
    agora = datetime.now(timezone.utc).isoformat()

    execucao_id = str(uuid.uuid4())
    execucao = Execucao(
        id=execucao_id,
        processadora=processadora_key,
        executada_em=agora,
        status="ok",
        total_convenios=1,
        success_count=1,
        error_count=0,
    )
    dado = DadoCorte(
        id=str(uuid.uuid4()),
        execucao_id=execucao_id,
        convenio_key=key,
        coletado_em=agora,
        convenio_nome=nome,
        data_corte=data_corte,
    )

    execucao_repo, dados_repo, _eventos = build_repositories()
    execucao_repo.salvar(execucao)
    dados_repo.salvar_lote([dado])

    logger.info("[manual] %s → data_corte=%r salvo", key, data_corte)
    return {"status": "ok", "convenio_key": key, "data_corte": data_corte}


@app.get("/coletas/{key}/eventos")
def listar_eventos(
    key: str,
    dias: int = Query(30, ge=1, le=365, description="Janela de dias para buscar eventos"),
) -> list[dict]:
    config = load_processadoras_config()
    processadora_key, _ = _resolver_key(key, config)
    _exec, _dados, repo = build_repositories()
    eventos = repo.listar(processadora_key, dias=dias)
    return [asdict(e) for e in eventos]


@app.get("/coletas/{key}/dados")
def obter_dados_atuais(key: str) -> list[dict]:
    config = load_processadoras_config()
    processadora_key, convenio_filter = _resolver_key(key, config)
    execucao_repo, dados_repo, _eventos = build_repositories()
    ultima = execucao_repo.buscar_ultima_ok(processadora_key)
    if not ultima:
        return []
    resultado = []
    for d in dados_repo.buscar_por_execucao(ultima.id):
        if convenio_filter and d.convenio_key != convenio_filter:
            continue
        d_dict = asdict(d)
        d_dict["data_corte"] = normalizar_data_corte(d.data_corte, d.mes_atual, d.coletado_em)
        resultado.append(d_dict)
    return resultado
