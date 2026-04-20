import json
from pathlib import Path


def load_processadoras_config() -> dict:
    config_path = Path(__file__).parent / "processadoras.json"
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)