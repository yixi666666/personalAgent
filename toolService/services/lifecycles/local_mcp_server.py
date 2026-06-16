import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from toolservice.models.mcp_lifecycle import McpLifecycle
from toolservice.models.states import McpServerState

logger = logging.getLogger(__name__)


class LocalMcpServer(McpLifecycle):
    """本地MCP服务器，实现 McpLifecycle 接口

    支持 stdio 和 SSE 两种传输方式：
    - stdio: 通过 mcp 库的 stdio_client 创建子进程并通信
    - sse:   通过 asyncio.create_subprocess_exec 创建子进程，再通过 HTTP+SSE 通信

    启动时按 retry 配置重试连接；运行时通过 health_check 检测进程状态，
    异常退出可调用 reconnect 自动重启。
    """

    def __init__(self, server_name: str, config: dict):
        self._server_name = server_name
        self.command = config.get("command")
        self.args = config.get("args", [])
        self.transport = config.get("transport", "stdio")
        self.env = config.get("env", {})
        self.workdir = config.get("workdir")
        self.url = config.get("url")  # SSE 传输需要

        retry_config = config.get("retry", {})
        self.max_attempts = retry_config.get("max_attempts", 3)
        self.delay_seconds = retry_config.get("delay_seconds", 5)

        # stdio 传输状态
        self._stdio_task: Optional[asyncio.Task] = None
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_ready: Optional[asyncio.Event] = None
        self._stdio_error: Optional[Exception] = None

        # SSE 传输状态
        self._process: Optional[asyncio.subprocess.Process] = None
        self._http_client = None  # RemoteMcpServer 实例

        # 公共状态
        self._lock: Optional[asyncio.Lock] = None
        self._tool_names: List[str] = []
        self._retry_count = 0
        self._state = McpServerState.DISCONNECTED

    # ==================== McpLifecycle 接口实现 ====================

    async def connect(self) -> List[dict]:
        """连接到 MCP 服务器，返回发现的工具列表。按 retry 配置重试。"""
        self._state = McpServerState.CONNECTING
        for attempt in range(1, self.max_attempts + 1):
            try:
                if self.transport == "stdio":
                    tools = await self._connect_stdio()
                elif self.transport == "sse":
                    tools = await self._connect_sse()
                else:
                    logger.error(f"本地MCP [{self._server_name}] 不支持的传输方式: {self.transport}")
                    self._state = McpServerState.ERROR
                    return []

                self._retry_count = 0
                self._state = McpServerState.CONNECTED
                logger.info(
                    f"本地MCP [{self._server_name}] 连接成功（{self.transport}），"
                    f"发现 {len(tools)} 个工具"
                )
                return tools

            except Exception as e:
                self._retry_count = attempt
                logger.warning(
                    f"本地MCP [{self._server_name}] 连接失败"
                    f"（第 {attempt}/{self.max_attempts} 次）: {e}"
                )
                # 连接失败时清理残留资源
                await self._cleanup()
                if attempt < self.max_attempts:
                    await asyncio.sleep(self.delay_seconds)

        self._state = McpServerState.ERROR
        logger.error(
            f"本地MCP [{self._server_name}] 超过最大重试次数 {self.max_attempts}，放弃连接"
        )
        return []

    async def shutdown(self) -> None:
        """优雅关闭连接/进程，释放资源"""
        self._state = McpServerState.SHUTTING_DOWN
        await self._cleanup()
        self._state = McpServerState.SHUTDOWN
        logger.info(f"本地MCP [{self._server_name}] 已关闭")

    async def health_check(self) -> bool:
        """检查连接/进程是否健康"""
        if self._state != McpServerState.CONNECTED:
            return False

        try:
            if self.transport == "stdio":
                if not self._session:
                    return False
                # 尝试 list_tools 探测会话是否存活
                await self._session.list_tools()
                return True
            elif self.transport == "sse":
                # 检查子进程是否存活
                if self._process and self._process.returncode is not None:
                    return False
                if self._http_client and self._http_client.is_failed:
                    return False
                return True
        except Exception as e:
            logger.warning(f"本地MCP [{self._server_name}] 健康检查失败: {e}")
            self._state = McpServerState.ERROR
            return False

        return False

    async def reconnect(self) -> List[dict]:
        """断开后重新连接，返回新的工具定义列表（可能已变化）"""
        logger.info(f"本地MCP [{self._server_name}] 正在重连...")
        old_tool_names = self._tool_names[:]
        await self._cleanup()
        self._tool_names = []
        self._state = McpServerState.DISCONNECTED
        tools = await self.connect()
        if tools:
            logger.info(
                f"本地MCP [{self._server_name}] 重连成功，"
                f"旧工具: {old_tool_names}，新工具: {self._tool_names}"
            )
        return tools

    async def list_tools(self) -> List[dict]:
        """在不重连的情况下，重新获取当前会话的工具列表"""
        if self.transport == "stdio" and self._session:
            return await self._discover_tools_stdio()
        elif self.transport == "sse" and self._http_client:
            return await self._discover_tools_sse()
        return []

    def get_session(self) -> Any:
        """返回可复用的会话，供工具调用"""
        if self.transport == "stdio":
            return self._session
        return self._http_client

    @property
    def state(self) -> McpServerState:
        return self._state

    @property
    def server_id(self) -> str:
        return self._server_name

    # ==================== 额外属性 ====================

    @property
    def is_failed(self) -> bool:
        """是否已超过最大重试次数"""
        return self._retry_count >= self.max_attempts

    @property
    def tool_names(self) -> List[str]:
        return self._tool_names

    def get_lock(self) -> Optional[asyncio.Lock]:
        """获取并发锁"""
        return self._lock

    # ==================== 内部实现 ====================

    async def _connect_stdio(self) -> List[dict]:
        """通过 stdio 方式连接

        使用后台任务持有 async with 上下文，确保 anyio 的 cancel scope 嵌套正确。
        stdio_client 和 ClientSession 必须在同一个 async with 链中管理，
        否则手动 __aenter__/__aexit__ 会破坏 anyio TaskGroup 的任务调度，
        导致 stdout_reader/stdin_writer 协程无法正常运行。
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env if self.env else None,
        )

        # 重置就绪事件
        self._stdio_ready = asyncio.Event()
        self._stdio_error = None

        # 启动后台任务持有 async with 上下文
        self._stdio_task = asyncio.create_task(
            self._stdio_lifecycle(server_params)
        )

        # 等待连接就绪或出错
        await self._stdio_ready.wait()

        if self._stdio_error:
            raise self._stdio_error

        return await self._discover_tools_stdio()

    async def _stdio_lifecycle(self, server_params):
        """后台任务：持有 stdio_client 和 ClientSession 的 async with 上下文"""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                self._read_stream = read_stream
                self._write_stream = write_stream
                async with ClientSession(read_stream, write_stream) as session:
                    # 初始化 MCP 协议握手
                    await session.initialize()
                    self._session = session
                    self._lock = asyncio.Lock()
                    # 通知连接就绪
                    self._stdio_ready.set()
                    # 保持上下文打开，直到任务被取消
                    await asyncio.Event().wait()
        except asyncio.CancelledError:
            # 正常关闭时任务被取消，忽略
            pass
        except Exception as e:
            self._stdio_error = e
            self._stdio_ready.set()

    async def _connect_sse(self) -> List[dict]:
        """通过 SSE 方式连接：启动子进程 + HTTP 通信"""
        if not self.url:
            raise ValueError(f"本地MCP [{self._server_name}] SSE 传输需要配置 url")

        # 启动子进程
        env = {**os.environ, **self.env} if self.env else None
        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            env=env,
            cwd=self.workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 等待子进程就绪（简单等待，后续可优化为端口探测）
        await asyncio.sleep(2)

        if self._process.returncode is not None:
            raise ConnectionError(
                f"本地MCP [{self._server_name}] 子进程启动后立即退出，"
                f"返回码: {self._process.returncode}"
            )

        # 通过 HTTP 连接
        from toolservice.services.lifecycles.remote_mcp_server import RemoteMcpServer

        self._http_client = RemoteMcpServer(self._server_name, self.url)
        connected = await self._http_client.connect()
        if not connected:
            raise ConnectionError(f"本地MCP [{self._server_name}] SSE 连接失败")

        self._lock = self._http_client._lock
        return await self._discover_tools_sse()

    async def _discover_tools_stdio(self) -> List[dict]:
        """从 stdio 会话发现工具"""
        result = await self._session.list_tools()
        tools = []
        self._tool_names = []
        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema if hasattr(tool, "inputSchema") else {},
            })
            self._tool_names.append(tool.name)
        return tools

    async def _discover_tools_sse(self) -> List[dict]:
        """从 SSE 客户端发现工具"""
        tools_data = await self._http_client.list_tools()
        tools = []
        self._tool_names = []
        for tool in tools_data:
            tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {}),
            })
            self._tool_names.append(tool["name"])
        return tools

    async def _cleanup(self):
        """清理所有连接和子进程资源"""
        # 清理 stdio 资源：取消后台生命周期任务
        if self._stdio_task and not self._stdio_task.done():
            self._stdio_task.cancel()
            try:
                await self._stdio_task
            except asyncio.CancelledError:
                pass
        self._stdio_task = None
        self._session = None
        self._read_stream = None
        self._write_stream = None

        # 清理 SSE 资源
        if self._http_client:
            try:
                await self._http_client.close()
            except Exception:
                pass
            self._http_client = None
        if self._process:
            try:
                if self._process.returncode is None:
                    self._process.terminate()
                    await asyncio.wait_for(self._process.wait(), timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

        self._lock = None
