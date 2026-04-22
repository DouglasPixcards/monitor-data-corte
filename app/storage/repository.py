from __future__ import annotations

from abc import ABC, abstractmethod


class StorageRepository(ABC):
    @abstractmethod
    def load_latest_snapshot(self, processadora: str) -> dict | None:
        pass

    @abstractmethod
    def save_execution(self, processadora: str, execution: dict) -> None:
        pass

    @abstractmethod
    def save_snapshot(self, processadora: str, snapshot: dict) -> None:
        pass

    @abstractmethod
    def save_latest_snapshot(self, processadora: str, snapshot: dict) -> None:
        pass

    @abstractmethod
    def append_events(self, processadora: str, events: list[dict]) -> None:
        pass