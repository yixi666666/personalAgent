import asyncio
import logging
from typing import Any, Dict

from toolservice.models.tool_lifecycle import ToolLifecycle
from toolservice.models.states import ToolState

logger = logging.getLogger(__name__)


class RemoteMcpToolLifecycle(ToolLifecycle):
    """远程MCP工具生命周期（HTTP+JSON-RPC）"""

    def __init__(self, server, tool_name: str, lock: asyncio.Lock):
        self._server = server
        self._tool_name = tool_name
        self._lock = lock
        self._state = ToolState.RUNNING  # 由服务器连接成功后创建，默认即可用
        self._server_id = server.server_id

    async def health_check(self) -> bool:
        if self._server.is_failed:
            self._state = ToolState.FATAL_ERROR
            return False
        return self._state == ToolState.RUNNING

    async def call(self, arguments: Dict[str, Any]) -> Any:
        async with self._lock:
            try:
                result = await self._server.call_tool(self._tool_name, arguments)
                return result
            except Exception as e:
                return {"error": {"code": "remote_mcp_error", "message": f"远程MCP工具调用失败: {e}"}}

    @property
    def state(self) -> ToolState:
        if self._server.is_failed and self._state == ToolState.RUNNING:
            self._state = ToolState.FATAL_ERROR
        return self._state

    @property
    def server_id(self) -> str:
        return self._server_id
