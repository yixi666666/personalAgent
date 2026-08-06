import asyncio
import logging
import os
from typing import Any, Dict, Optional

from capabilityService.models.mcp_lifecycle import McpLifecycle
from capabilityService.models.states import McpServerState

logger = logging.getLogger(__name__)


class RemoteMcpServer(McpLifecycle):
    """远程MCP服务器，通过HTTP+JSON-RPC连接

    实现 McpLifecycle 接口，管理远程MCP服务器连接。

    支持认证配置：
    - auth.type=bearer:  Authorization: Bearer <token>
    - auth.type=api_key: X-API-Key: <token>
    - auth.type=none 或缺省: 不附加认证头

    token 优先从 auth.token_env 指定的环境变量读取，其次使用 auth.token 字面值。
    """

    def __init__(self, name: str, url: str, max_retries: int = 5, auth_config: dict = None):
        self._name = name
        self._url = url
        self.max_retries = max_retries
        self._session_id = None
        self._http_client = None
        self._retry_count = 0
        self._lock = asyncio.Lock()
        self._state = McpServerState.DISCONNECTED

        # 解析认证配置
        self._auth_headers: Dict[str, str] = {}
        if auth_config:
            self._build_auth_headers(auth_config)

    def _build_auth_headers(self, auth_config: dict):
        """根据认证配置构建 HTTP 头"""
        auth_type = auth_config.get("type", "none").lower()

        # 优先从环境变量读取 token，其次使用字面值
        token = os.environ.get(auth_config.get("token_env", ""), "") if auth_config.get("token_env") else auth_config.get("token", "")

        if auth_type == "bearer" and token:
            self._auth_headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key" and token:
            header_name = auth_config.get("header_name", "X-API-Key")
            self._auth_headers[header_name] = token
        # auth_type == "none" 或无 token 时不附加认证头

    async def _get_http_client(self):
        import httpx
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    # ==================== McpLifecycle 接口实现 ====================

    async def connect(self) -> list[dict]:
        """建立连接，初始化会话。断连时自动重试，最多 max_retries 次"""
        self._state = McpServerState.CONNECTING
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._send_request("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": f"capabilityservice-{self._name}", "version": "1.0.0"},
                })
                if result:
                    self._session_id = result.get("sessionId")
                    await self._send_notification("notifications/initialized", {})
                    self._retry_count = 0
                    self._state = McpServerState.CONNECTED
                    # 连接成功后获取工具列表
                    return await self.list_tools()
                logger.warning(f"远程MCP [{self._name}] 连接返回空结果，第 {attempt}/{self.max_retries} 次重试")
            except Exception as e:
                logger.warning(f"远程MCP [{self._name}] 连接失败（第 {attempt}/{self.max_retries} 次）: {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(min(attempt * 2, 10))

        self._retry_count = self.max_retries
        self._state = McpServerState.ERROR
        logger.error(f"远程MCP [{self._name}] 超过最大重试次数 {self.max_retries}，放弃连接")
        return []

    async def shutdown(self) -> None:
        """优雅关闭连接，释放资源"""
        self._state = McpServerState.SHUTTING_DOWN
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._state = McpServerState.SHUTDOWN
        logger.info(f"远程MCP [{self._name}] 已关闭")

    async def health_check(self) -> bool:
        """检查连接是否健康"""
        if self._state != McpServerState.CONNECTED:
            return False
        try:
            # 尝试 list_tools 探测连接是否存活
            await self.list_tools()
            return True
        except Exception as e:
            logger.warning(f"远程MCP [{self._name}] 健康检查失败: {e}")
            self._state = McpServerState.ERROR
            return False

    async def reconnect(self) -> list[dict]:
        """断开后重新连接，返回新的工具定义列表"""
        logger.info(f"远程MCP [{self._name}] 正在重连...")
        # 关闭旧连接
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._session_id = None
        self._state = McpServerState.DISCONNECTED
        return await self.connect()

    async def list_tools(self) -> list[dict]:
        """获取工具列表"""
        result = await self._send_request("tools/list", {})
        if result and "tools" in result:
            return result["tools"]
        return []

    def get_session(self) -> Any:
        """返回可复用的会话（远程MCP返回自身，通过 call_tool 调用）"""
        return self

    @property
    def state(self) -> McpServerState:
        return self._state

    @property
    def server_id(self) -> str:
        return self._name

    # ==================== 额外方法 ====================

    @property
    def is_failed(self) -> bool:
        """是否已超过最大重试次数"""
        return self._retry_count >= self.max_retries

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """调用工具（锁由外部 lifecycle 管理，此处不加锁）"""
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
            # 附加认证头
            headers.update(self._auth_headers)

            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error(f"远程MCP [{self._name}] JSON-RPC错误: {data['error']}")
                return None

            return data.get("result")

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"远程MCP [{self._name}] 连接错误: {e}")
            self._retry_count += 1
            if self._retry_count >= self.max_retries:
                self._state = McpServerState.ERROR
                logger.error(f"远程MCP [{self._name}] 超过最大重试次数")
            else:
                try:
                    await self.connect()
                except Exception:
                    pass
            return None
        except Exception as e:
            logger.error(f"远程MCP [{self._name}] 请求失败: {e}")
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
            headers.update(self._auth_headers)
            await client.post(self._url, json=payload, headers=headers)
        except Exception as e:
            logger.warning(f"远程MCP [{self._name}] 通知发送失败: {e}")

    async def close(self):
        """关闭连接（兼容旧接口）"""
        await self.shutdown()
