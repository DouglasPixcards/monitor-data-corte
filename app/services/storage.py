import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
HISTORICO_PATH = DATA_DIR / "historico.json"
ULTIMO_RESULTADO_PATH = DATA_DIR / "ultimo_resultado.json"


def garantir_arquivos():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not HISTORICO_PATH.exists():
        HISTORICO_PATH.write_text("{}", encoding="utf-8")

    if not ULTIMO_RESULTADO_PATH.exists():
        ULTIMO_RESULTADO_PATH.write_text("{}", encoding="utf-8")


def carregar_historico() -> dict:
    garantir_arquivos()

    with open(HISTORICO_PATH, "r", encoding="utf-8") as arquivo:
        conteudo = arquivo.read().strip()

        if not conteudo:
            return {}

        return json.loads(conteudo)


def salvar_historico(dados: dict) -> None:
    garantir_arquivos()

    with open(HISTORICO_PATH, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=4, ensure_ascii=False)


def salvar_ultimo_resultado(dados: dict) -> None:
    garantir_arquivos()

    with open(ULTIMO_RESULTADO_PATH, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=4, ensure_ascii=False)