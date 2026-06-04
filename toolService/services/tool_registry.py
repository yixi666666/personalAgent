import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
import jsonschema

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    executor: Callable[..., Any]  # 接收关键字参数，返回结果


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
            executor=date_tool.execute,
        )
        logger.info(f"注册自研工具: {date_tool.name}")

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

            # 创建stdio连接
            read_stream, write_stream = await stdio_client(server_params).__anext__()
            session = ClientSession(read_stream, write_stream)
            await session.initialize()

            # 发现工具
            result = await session.list_tools()
            for tool in result.tools:
                executor = self._make_mcp_executor(session, tool.name)
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
                "read_stream": read_stream,
                "write_stream": write_stream,
                "lock": asyncio.Lock(),
            }
            self._tools = dict(self._tools)  # 触发更新
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
            for tool in tools:
                executor = self._make_remote_mcp_executor(client, tool["name"])
                self._tools[tool["name"]] = Tool(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=tool.get("inputSchema", {}),
                    executor=executor,
                )
                logger.info(f"从远程MCP [{server_name}] 注册工具: {tool['name']}")

            client_info = {
                "type": "remote",
                "client": client,
                "lock": asyncio.Lock(),
            }
            return client_info

        except Exception as e:
            logger.error(f"连接远程MCP服务器 {server_name} 失败: {e}")
            return None

    def _make_mcp_executor(self, session, tool_name: str) -> Callable:
        """为本地MCP工具创建执行函数"""
        async def executor(**kwargs):
            async with asyncio.Lock():
                try:
                    result = await session.call_tool(tool_name, arguments=kwargs)
                    if hasattr(result, 'content'):
                        # 处理MCP返回的content列表
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

    def _make_remote_mcp_executor(self, client, tool_name: str) -> Callable:
        """为远程MCP工具创建执行函数"""
        async def executor(**kwargs):
            try:
                result = await client.call_tool(tool_name, kwargs)
                return result
            except Exception as e:
                return {"error": {"code": "remote_mcp_error", "message": f"远程MCP工具调用失败: {e}"}}
        return executor

    def get_all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    async def execute_tool(self, name: str, arguments: dict) -> Any:
        """执行工具调用，带参数校验"""
        tool = self._tools.get(name)
        if not tool:
            return {"error": {"code": "tool_not_found", "message": f"未找到工具: {name}"}}

        # 参数校验
        if tool.parameters:
            try:
                jsonschema.validate(instance=arguments, schema=tool.parameters)
            except jsonschema.ValidationError as e:
                return {"error": {"code": "validation_error", "message": f"参数校验失败: {e.message}"}}

        # 执行工具
        try:
            import asyncio
            if asyncio.iscoroutinefunction(tool.executor):
                result = await tool.executor(**arguments)
            else:
                result = tool.executor(**arguments)
            return result
        except Exception as e:
            logger.error(f"工具执行失败 [{name}]: {e}")
            return {"error": {"code": "execution_error", "message": f"工具执行失败: {e}"}}

    async def shutdown(self):
        """关闭所有MCP连接"""
        for client_info in self._mcp_clients:
            try:
                if client_info["type"] == "local":
                    session = client_info.get("session")
                    if session:
                        await session.__aexit__(None, None, None)
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
        """建立连接，初始化会话"""
        try:
            result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": f"toolservice-{self.name}", "version": "1.0.0"},
            })
            if result:
                self._session_id = result.get("sessionId")
                # 发送initialized通知
                await self._send_notification("notifications/initialized", {})
                self._retry_count = 0
                return True
            return False
        except Exception as e:
            logger.error(f"远程MCP [{self.name}] 连接失败: {e}")
            self._retry_count += 1
            if self._retry_count >= self.max_retries:
                logger.error(f"远程MCP [{self.name}] 超过最大重试次数，放弃连接")
                return False
            return False

    async def list_tools(self) -> list[dict]:
        """获取工具列表"""
        result = await self._send_request("tools/list", {})
        if result and "tools" in result:
            return result["tools"]
        return []

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具"""
        async with self._lock:
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

        except httpx.HTTPStatusError as e:
            logger.error(f"远程MCP [{self.name}] HTTP错误: {e.response.status_code}")
            self._retry_count += 1
            return None
        except Exception as e:
            logger.error(f"远程MCP [{self.name}] 请求失败: {e}")
            self._retry_count += 1
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
