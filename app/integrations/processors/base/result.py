from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class IntegrationResult:
    status: Literal["ok", "erro"]
    processadora: str
    convenio: str | None
    dados: list[dict] = field(default_factory=list)
    erro: str | None = None
