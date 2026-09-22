import asyncio
import logging
from typing import Any, Dict

from capabilityService.models.tool_lifecycle import ToolLifecycle
from capabilityService.models.states import ToolState

logger = logging.getLogger(__name__)


class LocalMcpToolLifecycle(ToolLifecycle):
    """本地MCP工具生命周期（stdio传输）"""

    def __init__(self, session, tool_name: str, lock: asyncio.Lock, server_id: str):
        self._session = session
        self._tool_name = tool_name
        self._lock = lock
        self._state = ToolState.RUNNING  # 由服务器连接成功后创建，默认即可用
        self._server_id = server_id

    async def health_check(self) -> bool:
        return self._state == ToolState.RUNNING

    async def call(self, arguments: Dict[str, Any]) -> Any:
        async with self._lock:
            try:
                result = await self._session.call_tool(self._tool_name, arguments=arguments)
                if hasattr(result, 'content'):
                    texts = []
                    for item in result.content:
                        if hasattr(item, 'text'):
                            texts.append(item.text)
                        else:
                            texts.append(str(item))
                    return "\n".join(texts) if texts else str(result)
                return str(result)
            except Exception as e:
                return {"error": {"code": "mcp_error", "message": f"MCP工具调用失败: {e}"}}

    @property
    def state(self) -> ToolState:
        return self._state

    @property
    def server_id(self) -> str:
        return self._server_id
