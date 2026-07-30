from abc import ABC, abstractmethod
from typing import Any, Dict

from toolService.models.states import ToolState


class ToolLifecycle(ABC):
    """工具级别生命周期抽象接口"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查工具健康状态"""
        ...

    @abstractmethod
    async def call(self, arguments: Dict[str, Any]) -> Any:
        """工具执行"""
        ...

    @property
    @abstractmethod
    def state(self) -> ToolState:
        """工具状态枚举"""
        ...

    @property
    @abstractmethod
    def server_id(self) -> str:
        """所属服务器的唯一标识"""
        ...
