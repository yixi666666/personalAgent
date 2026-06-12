import asyncio
import functools
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import jsonschema

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    executor: Callable[..., Any]  # 接收关键字参数，返回结果（统一为异步函数）


def _ensure_async(func: Callable) -> Callable:
    """将同步函数包装为异步函数"""
    if asyncio.iscoroutinefunction(func):
        return func
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


class ToolRegistry:
    """统一工具注册表，管理自研工具、本地MCP工具和远程MCP工具"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._mcp_clients: list = []  # MCP客户端列表，用于shutdown时清理

    async def initialize(self):
        """初始化：注册自研工具，连接MCP服务器并发现工具"""
        from toolservice.config import get_config
        config = get_config()

        # 注册自研工具
        self._register_builtin_tools()

        # 连接本地MCP服务器
        mcp_servers = config.mcp_servers
        for server_name, server_cfg in mcp_servers.items():
            transport = server_cfg.get("transport", "stdio")
            try:
                if transport == "stdio":
                    client = await self._connect_local_mcp(server_name, server_cfg)
                    if client:
                        self._mcp_clients.append(client)
                elif transport == "http":
                    client = await self._connect_remote_mcp(server_name, server_cfg)
                    if client:
                        self._mcp_clients.append(client)
            except Exception as e:
                logger.error(f"连接MCP服务器 {server_name} 失败: {e}")

    def _register_builtin_tools(self):
        """注册自研工具"""
        from toolservice.tools.date_info import DateInfoTool
        date_tool = DateInfoTool()
        self._tools[date_tool.name] = Tool(
            name=date_tool.name,
            description=date_tool.description,
            parameters=date_tool.parameters,
            executor=_ensure_async(date_tool.execute),
        )
        logger.info(f"注册自研工具: {date_tool.name}")

        from toolservice.tools.rag_search import RagSearchTool
        rag_tool = RagSearchTool()
        self._tools[rag_tool.name] = Tool(
            name=rag_tool.name,
            description=rag_tool.description,
            parameters=rag_tool.parameters,
            executor=_ensure_async(rag_tool.execute),
        )
        logger.info(f"注册自研工具: {rag_tool.name}")

    async def _connect_local_mcp(self, server_name: str, server_cfg: dict) -> Optional[Any]:
        """通过stdio方式连接本地MCP服务器"""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            command = server_cfg.get("command", "python")
            args = server_cfg.get("args", [])
            env = server_cfg.get("env", {})

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env if env else None,
            )

            # 使用async with上下文管理器创建stdio连接，确保子进程可被正确清理
            stdio_ctx = stdio_client(server_params)
            read_stream, write_stream = await stdio_ctx.__aenter__()
            session = ClientSession(read_stream, write_stream)
            await session.initialize()

            # 为该客户端创建锁
            client_lock = asyncio.Lock()

            # 发现工具
            result = await session.list_tools()
            for tool in result.tools:
                executor = self._make_mcp_executor(session, tool.name, client_lock)
                self._tools[tool.name] = Tool(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                    executor=executor,
                )
                logger.info(f"从本地MCP [{server_name}] 注册工具: {tool.name}")

            # 包装客户端信息用于后续清理
            client_info = {
                "type": "local",
                "session": session,
                "stdio_ctx": stdio_ctx,
                "read_stream": read_stream,
                "write_stream": write_stream,
                "lock": client_lock,
                "tool_names": [tool.name for tool in result.tools],
            }
            return client_info

        except Exception as e:
            logger.error(f"连接本地MCP服务器 {server_name} 失败: {e}")
            return None

    async def _connect_remote_mcp(self, server_name: str, server_cfg: dict) -> Optional[Any]:
        """通过HTTP+JSON-RPC连接远程MCP服务器"""
        try:
            url = server_cfg.get("url", "")
            if not url:
                logger.error(f"远程MCP服务器 {server_name} 缺少url配置")
                return None

            client = RemoteMCPClient(server_name, url)
            connected = await client.connect()
            if not connected:
                return None

            # 发现工具
            tools = await client.list_tools()
            tool_names = []
            for tool in tools:
                name = tool["name"]
                executor = self._make_remote_mcp_executor(client, name, client._lock)
                self._tools[name] = Tool(
                    name=name,
                    description=tool.get("description", ""),
                    parameters=tool.get("inputSchema", {}),
                    executor=executor,
                )
                tool_names.append(name)
                logger.info(f"从远程MCP [{server_name}] 注册工具: {name}")

            client_info = {
                "type": "remote",
                "client": client,
                "lock": client._lock,
                "tool_names": tool_names,
            }
            return client_info

        except Exception as e:
            logger.error(f"连接远程MCP服务器 {server_name} 失败: {e}")
            return None

    def _make_mcp_executor(self, session, tool_name: str, lock: asyncio.Lock) -> Callable:
        """为本地MCP工具创建执行函数，使用客户端级别的锁"""
        async def executor(**kwargs):
            async with lock:
                try:
                    result = await session.call_tool(tool_name, arguments=kwargs)
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
        return executor

    def _make_remote_mcp_executor(self, client, tool_name: str, lock: asyncio.Lock) -> Callable:
        """为远程MCP工具创建执行函数，使用客户端级别的锁"""
        async def executor(**kwargs):
            async with lock:
                try:
                    result = await client.call_tool(tool_name, kwargs)
                    return result
                except Exception as e:
                    return {"error": {"code": "remote_mcp_error", "message": f"远程MCP工具调用失败: {e}"}}
        return executor

    def _remove_tools_by_names(self, tool_names: list[str]):
        """从注册表中移除指定名称的工具"""
        for name in tool_names:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"已移除工具: {name}")

    def get_all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    async def execute_tool(self, name: str, arguments: dict) -> Any:
        """执行工具调用，带参数校验"""
        tool = self._tools.get(name)
        if not tool:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: tool_not_found")
            return {"error": {"code": "tool_not_found", "message": f"未找到工具: {name}"}}

        # 强制参数校验
        try:
            jsonschema.validate(instance=arguments, schema=tool.parameters)
        except jsonschema.ValidationError as e:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: validation_error - {e.message}")
            return {"error": {"code": "validation_error", "message": f"参数校验失败: {e.message}"}}

        # 执行工具
        try:
            result = await tool.executor(**arguments)
            # debug模式下打印工具调用信息（一行输出）
            result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result).replace('\n', '; ')
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 结果: {result_str}")

            # 检查远程MCP客户端是否超过重试次数，如果是则移除其工具
            self._check_and_remove_failed_clients()

            return result
        except Exception as e:
            logger.debug(f"工具调用 | 名称: {name} | 参数: {json.dumps(arguments, ensure_ascii=False)} | 错误: execution_error - {e}")
            logger.error(f"工具执行失败 [{name}]: {e}")
            return {"error": {"code": "execution_error", "message": f"工具执行失败: {e}"}}

    def _check_and_remove_failed_clients(self):
        """检查远程MCP客户端是否超过重试次数，移除其注册的工具"""
        clients_to_remove = []
        for client_info in self._mcp_clients:
            if client_info["type"] == "remote":
                client = client_info.get("client")
                if client and client.is_failed:
                    tool_names = client_info.get("tool_names", [])
                    self._remove_tools_by_names(tool_names)
                    clients_to_remove.append(client_info)

        for client_info in clients_to_remove:
            self._mcp_clients.remove(client_info)
            logger.warning(f"远程MCP [{client_info.get('client').name}] 超过最大重试次数，已移除其所有工具")

    async def shutdown(self):
        """关闭所有MCP连接，终结子进程"""
        for client_info in self._mcp_clients:
            try:
                if client_info["type"] == "local":
                    session = client_info.get("session")
                    if session:
                        await session.__aexit__(None, None, None)
                    # 显式关闭stdio上下文，终结子进程
                    stdio_ctx = client_info.get("stdio_ctx")
                    if stdio_ctx:
                        try:
                            await stdio_ctx.__aexit__(None, None, None)
                        except Exception:
                            pass
                elif client_info["type"] == "remote":
                    client = client_info.get("client")
                    if client:
                        await client.close()
            except Exception as e:
                logger.warning(f"关闭MCP客户端失败: {e}")
        self._mcp_clients.clear()
        logger.info("所有MCP连接已关闭")


class RemoteMCPClient:
    """远程MCP客户端，通过HTTP+JSON-RPC连接"""

    def __init__(self, name: str, url: str, max_retries: int = 5):
        self.name = name
        self.url = url
        self.max_retries = max_retries
        self._session_id = None
        self._http_client = None
        self._retry_count = 0
        self._lock = asyncio.Lock()

    async def _get_http_client(self):
        import httpx
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def connect(self) -> bool:
        """建立连接，初始化会话。断连时自动重试，最多 max_retries 次"""
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._send_request("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": f"toolservice-{self.name}", "version": "1.0.0"},
                })
                if result:
                    self._session_id = result.get("sessionId")
                    await self._send_notification("notifications/initialized", {})
                    self._retry_count = 0
                    return True
                logger.warning(f"远程MCP [{self.name}] 连接返回空结果，第 {attempt}/{self.max_retries} 次重试")
            except Exception as e:
                logger.warning(f"远程MCP [{self.name}] 连接失败（第 {attempt}/{self.max_retries} 次）: {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(min(attempt * 2, 10))

        self._retry_count = self.max_retries
        logger.error(f"远程MCP [{self.name}] 超过最大重试次数 {self.max_retries}，放弃连接")
        return False

    @property
    def is_failed(self) -> bool:
        """是否已超过最大重试次数"""
        return self._retry_count >= self.max_retries

    async def list_tools(self) -> list[dict]:
        """获取工具列表"""
        result = await self._send_request("tools/list", {})
        if result and "tools" in result:
            return result["tools"]
        return []

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具（锁由外部 executor 管理，此处不加锁）"""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        if result:
            if "content" in result:
                texts = []
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
                    else:
                        texts.append(str(item))
                return "\n".join(texts) if texts else str(result)
            return result
        return {"error": {"code": "empty_result", "message": "工具返回空结果"}}

    async def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """发送JSON-RPC请求"""
        import httpx
        try:
            client = await self._get_http_client()
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            }
            headers = {"Content-Type": "application/json"}
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id

            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error(f"远程MCP [{self.name}] JSON-RPC错误: {data['error']}")
                return None

            return data.get("result")

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"远程MCP [{self.name}] 连接错误: {e}")
            # 连接类错误，尝试重连
            self._retry_count += 1
            if self._retry_count >= self.max_retries:
                logger.error(f"远程MCP [{self.name}] 超过最大重试次数")
            else:
                try:
                    await self.connect()
                except Exception:
                    pass
            return None
        except Exception as e:
            logger.error(f"远程MCP [{self.name}] 请求失败: {e}")
            return None

    async def _send_notification(self, method: str, params: dict):
        """发送JSON-RPC通知（无id，不期待响应）"""
        import httpx
        try:
            client = await self._get_http_client()
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
            headers = {"Content-Type": "application/json"}
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id
            await client.post(self.url, json=payload, headers=headers)
        except Exception as e:
            logger.warning(f"远程MCP [{self.name}] 通知发送失败: {e}")

    async def close(self):
        """关闭连接"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
