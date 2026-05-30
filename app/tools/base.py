from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> list[dict]:
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        pass

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
