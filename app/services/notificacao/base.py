from __future__ import annotations

from abc import ABC, abstractmethod


class NotificadorBase(ABC):
    @abstractmethod
    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None: ...
