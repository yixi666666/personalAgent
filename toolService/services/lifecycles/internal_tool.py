import logging
from typing import Any, Callable, Dict

from toolService.models.tool_lifecycle import ToolLifecycle
from toolService.models.states import ToolState
from toolService.models.tool import _ensure_async

logger = logging.getLogger(__name__)


class InternalToolLifecycle(ToolLifecycle):
    """内部工具生命周期（自研工具）"""

    def __init__(self, executor: Callable, server_id: str = "internal"):
        self._executor = _ensure_async(executor)
        self._state = ToolState.RUNNING  # 自研工具默认即可用
        self._server_id = server_id

    async def health_check(self) -> bool:
        return self._state == ToolState.RUNNING

    async def call(self, arguments: Dict[str, Any]) -> Any:
        return await self._executor(**arguments)

    @property
    def state(self) -> ToolState:
        return self._state

    @property
    def server_id(self) -> str:
        return self._server_id
