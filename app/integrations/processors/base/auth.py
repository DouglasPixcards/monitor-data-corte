from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ApiCredentials:
    username: str
    password: str


class ApiAuthStrategy(ABC):
    @abstractmethod
    def authenticate(self) -> str:
        """Autentica e retorna o token de acesso."""
