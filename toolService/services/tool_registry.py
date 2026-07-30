import asyncio
import importlib
import json
import logging
from typing import Any, Dict, List, Optional

import jsonschema

from toolService.models.states import McpServerState, ToolState
from toolService.models.tool import Tool
from toolService.services.lifecycles.internal_tool import InternalToolLifecycle
from toolService.services.lifecycles.local_mcp_tool import LocalMcpToolLifecycle
from toolService.services.lifecycles.remote_mcp_tool import RemoteMcpToolLifecycle
from toolService.services.lifecycles.local_mcp_server import LocalMcpServer
from toolService.services.lifecycles.remote_mcp_server import RemoteMcpServer

logger = logging.getLogger(__name__)

# 后台健康检查间隔（秒）
HEALTH_CHECK_INTERVAL = 30


class ToolRegistry:
    """统一工具注册表，管理自研工具、本地MCP工具和远程MCP工具

    所有工具的注册均由 tools.yaml 驱动：
    - internal_tools: 自研工具，通过 handler 路径动态导入
    - local_mcp:     本地MCP工具，通过 LocalMcpServer 管理子进程
    - remote_mcp:    远程MCP工具，通过 RemoteMcpServer 通信
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._local_mcp_servers: List[LocalMcpServer] = []
        self._remote_mcp_clients: List[dict] = []
        self._monitor_task: Optional[asyncio.Task] = None

    # ==================== 初始化 ====================

    async def initialize(self):
        """初始化：按 tools.yaml 配置注册所有工具"""
        from toolService.config import get_config
        config = get_config()

        # 1. 注册自研工具
        await self._register_internal_tools(config.internal_tools)

        # 2. 连接本地 MCP 服务器
        await self._connect_local_mcp_servers(config.local_mcp)

        # 3. 连接远程 MCP 服务器
        await self._connect_remote_mcp_servers(config.remote_mcp)

        # 4. 启动后台健康监控
        self._monitor_task = asyncio.create_task(self._health_monitor())

    # ==================== 自研工具 ====================

    async def _register_internal_tools(self, tool_configs: list[dict]):
        """根据配置动态导入并注册自研工具"""
        for tool_cfg in tool_configs:
            name = tool_cfg.get("name")
            handler_path = tool_cfg.get("handler")
            if not name or not handler_path:
                logger.warning(f"自研工具配置缺少 name 或 handler: {tool_cfg}")
                continue

            try:
                tool_instance = self._import_tool_class(handler_path)()
                lifecycle = InternalToolLifecycle(tool_instance.execute, server_id="internal")
                self._tools[tool_instance.name] = Tool(
                    name=tool_instance.name,
                    description=tool_instance.description,
                    parameters=tool_instance.parameters,
                    lifecycle=lifecycle,
                )
                logger.info(f"注册自研工具: {tool_instance.name} (handler: {handler_path})")
            except Exception as e:
                logger.error(f"注册自研工具 {name} 失败 (handler: {handler_path}): {e}")

    @staticmethod
    def _import_tool_class(dotted_path: str):
        """动态导入工具类，格式: 模块.类名"""
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    # ==================== 本地 MCP ====================

    async def _connect_local_mcp_servers(self, server_configs: list[dict]):
        """连接所有本地 MCP 服务器"""
        for server_cfg in server_configs:
            server_name = server_cfg.get("name")
            if not server_name:
                logger.warning(f"本地MCP配置缺少 name: {server_cfg}")
                continue

            server = LocalMcpServer(server_name, server_cfg)
            tools = await server.connect()

            if not tools:
                if server.is_failed:
                    self._local_mcp_servers.append(server)
                continue

            # 注册发现的工具
            await self._register_local_mcp_tools(server, tools)
            self._local_mcp_servers.append(server)

    async def _register_local_mcp_tools(self, server: LocalMcpServer, tools: list[dict]):
        """将 LocalMcpServer 发现的工具注册到注册表"""
        for tool_info in tools:
            if server.transport == "stdio":
                lifecycle = LocalMcpToolLifecycle(
                    server.get_session(), tool_info["name"], server.get_lock(), server.server_id
                )
            else:  # sse
                lifecycle = RemoteMcpToolLifecycle(
                    server.get_session(), tool_info["name"], server.get_lock()
                )
            self._tools[tool_info["name"]] = Tool(
                name=tool_info["name"],
                description=tool_info["description"],
                parameters=tool_info["parameters"],
                lifecycle=lifecycle,
            )
            logger.info(f"从本地MCP [{server.server_id}] 注册工具: {tool_info['name']}")

    # ==================== 远程 MCP ====================

    async def _connect_remote_mcp_servers(self, server_configs: list[dict]):
        """连接所有远程 MCP 服务器"""
        for server_cfg in server_configs:
            server_name = server_cfg.get("name")
            url = server_cfg.get("url", "")
            if not server_name or not url:
                logger.warning(f"远程MCP配置缺少 name 或 url: {server_cfg}")
                continue

            max_retries = server_cfg.get("max_retries", 5)
            auth_config = server_cfg.get("auth", {})

            try:
                client = RemoteMcpServer(
                    server_name, url,
                    max_retries=max_retries,
                    auth_config=auth_config,
                )
                tools = await client.connect()
                if not tools:
                    self._remote_mcp_clients.append({
                        "client": client,
                        "tool_names": [],
                    })
                    continue

                # 注册发现的工具
                tool_names = []
                for tool in tools:
                    name = tool["name"]
                    lifecycle = RemoteMcpToolLifecycle(client, name, client._lock)
                    self._tools[name] = Tool(
                        name=name,
                        description=tool.get("description", ""),
                        parameters=tool.get("inputSchema", {}),
                        lifecycle=lifecycle,
                    )
                    tool_names.append(name)
                    logger.info(f"从远程MCP [{server_name}] 注册工具: {name}")

                self._remote_mcp_clients.append({
                    "client": client,
                    "tool_names": tool_names,
                })

            except Exception as e:
                logger.error(f"连接远程MCP服务器 {server_name} 失败: {e}")

    # ==================== 后台健康监控 ====================

    async def _health_monitor(self):
        """后台定期检查本地 MCP 进程健康状态，异常时自动重启"""
        while True:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                await self._check_local_mcp_health()
                self._check_and_remove_failed_remote_clients()
            except asyncio.CancelledError:
                logger.info("健康监控任务已取消")
                return
            except Exception as e:
                logger.error(f"健康监控异常: {e}")

    async def _check_local_mcp_health(self):
        """检查本地 MCP 进程健康状态，不健康的尝试重启"""
        for server in self._local_mcp_servers:
            if server.state != McpServerState.CONNECTED:
                continue

            healthy = await server.health_check()
            if healthy:
                continue

            logger.warning(
                f"本地MCP [{server.server_id}] 健康检查失败，"
                f"当前工具: {server.tool_names}，尝试重启..."
            )

            # 标记旧工具为 UNHEALTHY
            for tool_name in server.tool_names:
                tool = self._tools.get(tool_name)
                if tool and hasattr(tool.lifecycle, "_state"):
                    tool.lifecycle._state = ToolState.UNHEALTHY

            # 尝试重连
            if not server.is_failed:
                new_tools = await server.reconnect()
                if new_tools:
                    # 移除旧工具，注册新工具
                    self._remove_tools_by_names(server.tool_names)
                    for tool_info in new_tools:
                        if server.transport == "stdio":
                            lifecycle = LocalMcpToolLifecycle(
                                server.get_session(), tool_info["name"], server.get_lock(), server.server_id
                            )
                        else:
                            lifecycle = RemoteMcpToolLifecycle(
                                server.get_session(), tool_info["name"], server.get_lock()
                            )
                        self._tools[tool_info["name"]] = Tool(
                            name=tool_info["name"],
                            description=tool_info["description"],
                            parameters=tool_info["parameters"],
                            lifecycle=lifecycle,
                        )
                    logger.info(
                        f"本地MCP [{server.server_id}] 重启成功，"
                        f"重新注册 {len(new_tools)} 个工具"
                    )
                else:
                    logger.error(
                        f"本地MCP [{server.server_id}] 重启失败，"
                        f"重试次数已用尽"
                    )
                    # 标记工具为 FATAL_ERROR
                    for tool_name in server.tool_names:
                        tool = self._tools.get(tool_name)
                        if tool and hasattr(tool.lifecycle, "_state"):
                            tool.lifecycle._state = ToolState.FATAL_ERROR

    # ==================== 工具查询与执行 ====================

    def get_all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    async def execute_tool(self, name: str, arguments: dict) -> Any:
        """执行工具调用，带参数校验和状态检查"""
        tool = self._tools.get(name)
        if not tool:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: tool_not_found")
            return {"error": {"code": "tool_not_found", "message": f"未找到工具: {name}"}}

        # 检查工具状态
        if tool.lifecycle.state != ToolState.RUNNING:
            logger.debug(f"工具调用 | 名称: {name} | 状态: {tool.lifecycle.state} | 错误: tool_not_available")
            return {"error": {"code": "tool_not_available", "message": f"工具不可用，当前状态: {tool.lifecycle.state}"}}

        # 强制参数校验
        try:
            jsonschema.validate(instance=arguments, schema=tool.parameters)
        except jsonschema.ValidationError as e:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: validation_error - {e.message}")
            return {"error": {"code": "validation_error", "message": f"参数校验失败: {e.message}"}}

        # 执行工具
        try:
            result = await tool.execute(**arguments)
            # debug模式下打印工具调用信息（一行输出）
            result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result).replace('\n', '; ')
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 结果: {result_str}")

            # 检查远程MCP客户端是否超过重试次数
            self._check_and_remove_failed_remote_clients()

            return result
        except Exception as e:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: execution_error - {e}")
            logger.error(f"工具执行失败 [{name}]: {e}")
            return {"error": {"code": "execution_error", "message": f"工具执行失败: {e}"}}

    # ==================== 健康检查 ====================

    async def health_check_all(self) -> Dict[str, ToolState]:
        """检查所有工具的健康状态"""
        states = {}
        for name, tool in self._tools.items():
            await tool.lifecycle.health_check()
            states[name] = tool.lifecycle.state
        return states

    # ==================== 远程 MCP 失败处理 ====================

    def _check_and_remove_failed_remote_clients(self):
        """检查远程MCP客户端是否超过重试次数，移除其注册的工具"""
        clients_to_remove = []
        for client_info in self._remote_mcp_clients:
            client = client_info.get("client")
            if client and client.is_failed:
                tool_names = client_info.get("tool_names", [])
                for tname in tool_names:
                    tool = self._tools.get(tname)
                    if tool and isinstance(tool.lifecycle, RemoteMcpToolLifecycle):
                        tool.lifecycle._state = ToolState.FATAL_ERROR
                self._remove_tools_by_names(tool_names)
                clients_to_remove.append(client_info)

        for client_info in clients_to_remove:
            self._remote_mcp_clients.remove(client_info)
            logger.warning(f"远程MCP [{client_info.get('client').server_id}] 超过最大重试次数，已移除其所有工具")

    # ==================== 工具移除 ====================

    def _remove_tools_by_names(self, tool_names: list[str]):
        """从注册表中移除指定名称的工具"""
        for name in tool_names:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"已移除工具: {name}")

    # ==================== 关闭 ====================

    async def shutdown(self):
        """关闭所有MCP服务器连接，终结子进程"""
        # 取消健康监控任务
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # 关闭本地 MCP 服务器（含子进程）
        for server in self._local_mcp_servers:
            try:
                await server.shutdown()
            except Exception as e:
                logger.warning(f"关闭本地MCP [{server.server_id}] 失败: {e}")

        # 关闭远程 MCP 客户端
        for client_info in self._remote_mcp_clients:
            try:
                client = client_info.get("client")
                if client:
                    await client.shutdown()
            except Exception as e:
                logger.warning(f"关闭远程MCP客户端失败: {e}")

        self._local_mcp_servers.clear()
        self._remote_mcp_clients.clear()
        self._tools.clear()
        logger.info("所有MCP连接已关闭")


# ==================== 单例 ====================

_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
