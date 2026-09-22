import asyncio
import functools
from dataclasses import dataclass
from typing import Any, Callable, Dict

from capabilityService.models.tool_lifecycle import ToolLifecycle


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    lifecycle: ToolLifecycle  # 工具生命周期实例

    async def execute(self, **kwargs) -> Any:
        """Agent 调用入口，委托给生命周期实例执行"""
        return await self.lifecycle.call(kwargs)


def _ensure_async(func: Callable) -> Callable:
    """将同步函数包装为异步函数"""
    if asyncio.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
