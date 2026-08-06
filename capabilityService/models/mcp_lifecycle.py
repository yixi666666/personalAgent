from abc import ABC, abstractmethod
from typing import Any

from capabilityService.models.states import McpServerState


class McpLifecycle(ABC):
    """MCP进程级别生命周期抽象接口"""

    @abstractmethod
    async def connect(self) -> list[dict]:
        """建立连接，完成 MCP 握手，返回工具定义列表"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """优雅关闭连接/进程，释放资源"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查连接/进程是否健康"""
        ...

    @abstractmethod
    async def reconnect(self) -> list[dict]:
        """断开后重新连接，返回新的工具定义列表（可能已变化）"""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """在不重连的情况下，重新获取当前会话的工具列表"""
        ...

    @abstractmethod
    def get_session(self) -> Any:
        """返回可复用的会话，供工具调用"""
        ...

    @property
    @abstractmethod
    def state(self) -> McpServerState:
        """服务器级别状态"""
        ...

    @property
    @abstractmethod
    def server_id(self) -> str:
        """唯一标识，用于注册表和日志"""
        ...
