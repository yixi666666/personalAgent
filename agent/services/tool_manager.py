import asyncio
import json
import logging
from typing import Optional
import httpx
import jsonschema
from agent.config import get_config

logger = logging.getLogger(__name__)


class ToolManager:
    """从toolService获取工具列表，缓存，校验参数，并行执行工具调用"""

    def __init__(self):
        config = get_config()
        self._toolservice_url = config.toolservice_url
        self._call_timeout = config.tool_call_timeout
        self._tools: dict[str, dict] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._refresh_interval = config.toolservice_refresh_interval

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def refresh_tools(self):
        """调用 GET http://localhost:8003/tools/list 刷新工具缓存"""
        try:
            client = await self._get_http_client()
            url = f"{self._toolservice_url}/tools/list"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            tools_list = data.get("tools", [])
            new_tools = {}
            for tool in tools_list:
                name = tool.get("name", "")
                if name:
                    new_tools[name] = {
                        "name": name,
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
            self._tools = new_tools
            logger.info(f"工具列表已刷新，共 {len(self._tools)} 个工具: {list(self._tools.keys())}")
        except httpx.HTTPStatusError as e:
            logger.error(f"获取工具列表失败: HTTP {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"获取工具列表失败: {e}")
            raise

    def start_refresh_task(self):
        """启动定时刷新工具列表的后台任务"""
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._periodic_refresh())

    def stop_refresh_task(self):
        """停止定时刷新任务"""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()

    async def _periodic_refresh(self):
        """定期刷新工具列表"""
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self.refresh_tools()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"定时刷新工具列表失败: {e}")

    async def get_tool_schemas_for_llm(self) -> list[dict]:
        """返回格式化后的工具列表，用于发送给大模型

        如果缓存为空，先尝试刷新一次
        """
        if not self._tools:
            await self.refresh_tools()
        schemas = []
        for name, tool_info in self._tools.items():
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool_info["description"],
                    "parameters": tool_info["parameters"],
                },
            }
            schemas.append(schema)
        return schemas

    async def execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """
        并行执行所有工具调用
        - 遍历 tool_calls 数组，为每一项构建一个 async 任务
        - 使用 asyncio.gather 并行等待所有任务
        - 每个任务内部设置 10 秒超时，超时或异常时返回统一错误字典
        - 将所有返回（无论成败）打包成 tool 消息
        """
        tasks = [self._execute_single_tool(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_messages = []
        for i, result in enumerate(results):
            tc = tool_calls[i]
            tool_call_id = tc.get("id", f"call_{i}")
            tool_name = tc.get("function", {}).get("name", "unknown")

            if isinstance(result, Exception):
                tool_messages.append({
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(
                        {"code": "error", "message": f"工具执行异常: {str(result)}"},
                        ensure_ascii=False,
                    ),
                })
            else:
                tool_messages.append(result)

        return tool_messages

    async def _execute_single_tool(self, tool_call: dict) -> dict:
        """
        执行单个工具调用
        - 使用 jsonschema 校验参数
        - 参数不合法则返回错误信息
        - 校验通过后转发到 POST http://localhost:8003/tools/call
        """
        tool_call_id = tool_call.get("id", "call_unknown")
        function_info = tool_call.get("function", {})
        tool_name = function_info.get("name", "unknown")
        arguments_str = function_info.get("arguments", "{}")

        try:
            if isinstance(arguments_str, str):
                arguments = json.loads(arguments_str)
            else:
                arguments = arguments_str
        except json.JSONDecodeError as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    {"code": "invalid_arguments", "message": f"参数JSON解析失败: {e}"},
                    ensure_ascii=False,
                ),
            }

        tool_info = self._tools.get(tool_name)
        if not tool_info:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    {"code": "tool_not_found", "message": f"未找到工具: {tool_name}"},
                    ensure_ascii=False,
                ),
            }

        parameters_schema = tool_info.get("parameters", {})
        if parameters_schema:
            try:
                jsonschema.validate(instance=arguments, schema=parameters_schema)
            except jsonschema.ValidationError as e:
                return {
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(
                        {
                            "code": "validation_error",
                            "message": f"参数校验失败: {e.message}",
                        },
                        ensure_ascii=False,
                    ),
                }

        try:
            client = await self._get_http_client()
            url = f"{self._toolservice_url}/tools/call"
            payload = {"name": tool_name, "arguments": arguments}
            response = await asyncio.wait_for(
                client.post(url, json=payload),
                timeout=self._call_timeout,
            )
            response.raise_for_status()
            result_data = response.json()

            if result_data.get("error"):
                content = json.dumps(
                    {"code": "tool_error", "message": result_data["error"].get("message", "工具执行失败")},
                    ensure_ascii=False,
                )
            else:
                content = json.dumps(result_data.get("result", ""), ensure_ascii=False)

            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": content,
            }
        except asyncio.TimeoutError:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    {"code": "timeout", "message": f"工具调用超时 ({self._call_timeout}秒)"},
                    ensure_ascii=False,
                ),
            }
        except httpx.HTTPStatusError as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    {"code": "http_error", "message": f"工具服务返回错误: HTTP {e.response.status_code}"},
                    ensure_ascii=False,
                ),
            }
        except Exception as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(
                    {"code": "error", "message": f"工具执行失败: {str(e)}"},
                    ensure_ascii=False,
                ),
            }


_tool_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager
