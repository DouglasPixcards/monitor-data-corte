from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAuthStrategy(ABC):
    @abstractmethod
    def authenticate(self, scraper) -> None:
        pass