import json
import logging
from typing import Optional
from app.tools.base import BaseTool
from app.tools.date_info import DateInfo
from app.services.llm_client import get_llm_client
from app.services.conversation import get_conversation_manager
from app.config import get_config

logger = logging.getLogger(__name__)


class ToolEngine:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._register_tools()

    def _register_tools(self):
        config = get_config()
        if not config.tools_enabled:
            return
        tool_instances = [DateInfo()]
        for tool in tool_instances:
            self._tools[tool.name] = tool

    def get_all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        tool = self.get_tool(tool_name)
        if not tool:
            return f"错误：未找到工具 '{tool_name}'"
        try:
            result = tool.execute(**tool_args)
            return result
        except Exception as e:
            logger.error(f"工具执行失败 [{tool_name}]: {e}")
            return f"工具执行失败: {e}"

    def analyze_and_execute(
        self, messages: list[dict], conversation_id: str
    ) -> dict:
        llm_client = get_llm_client()
        conv_manager = get_conversation_manager()

        analysis = llm_client.analyze_tool_need(messages)

        need_tool = analysis.get("need_tool", False)
        tool_name = analysis.get("tool_name")
        tool_args = analysis.get("tool_args", {})

        tool_call_records = []

        if need_tool and tool_name:
            logger.info(f"需要调用工具: {tool_name}, 参数: {tool_args}")
            tool_result = self.execute_tool(tool_name, tool_args)
            conv_manager.save_tool_call(
                conversation_id,
                tool_name,
                json.dumps(tool_args, ensure_ascii=False),
                tool_result,
            )
            tool_call_records.append(
                {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "result": tool_result,
                }
            )
            summary_messages = messages + [
                {
                    "role": "assistant",
                    "content": f"我调用了工具 {tool_name}，获取到了以下信息：{tool_result}",
                },
                {
                    "role": "user",
                    "content": "请根据工具返回的结果，给出完整的回答。",
                },
            ]
            llm_result = llm_client.chat(summary_messages)
            final_content = llm_result["choices"][0]["message"]["content"]
        else:
            llm_result = llm_client.chat(messages)
            final_content = llm_result["choices"][0]["message"]["content"]

        return {
            "content": final_content,
            "tool_calls": tool_call_records,
            "usage": llm_result.get("usage", {}),
        }


    def prepare_for_streaming(
        self, messages: list[dict], conversation_id: str
    ) -> dict:
        llm_client = get_llm_client()
        conv_manager = get_conversation_manager()

        analysis = llm_client.analyze_tool_need(messages)

        need_tool = analysis.get("need_tool", False)
        tool_name = analysis.get("tool_name")
        tool_args = analysis.get("tool_args", {})

        tool_call_records = []
        final_messages = messages

        if need_tool and tool_name:
            logger.info(f"需要调用工具: {tool_name}, 参数: {tool_args}")
            tool_result = self.execute_tool(tool_name, tool_args)
            conv_manager.save_tool_call(
                conversation_id,
                tool_name,
                json.dumps(tool_args, ensure_ascii=False),
                tool_result,
            )
            tool_call_records.append(
                {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "result": tool_result,
                }
            )
            final_messages = messages + [
                {
                    "role": "assistant",
                    "content": f"我调用了工具 {tool_name}，获取到了以下信息：{tool_result}",
                },
                {
                    "role": "user",
                    "content": "请根据工具返回的结果，给出完整的回答。",
                },
            ]

        return {
            "messages": final_messages,
            "tool_calls": tool_call_records,
        }


_tool_engine: Optional[ToolEngine] = None


def get_tool_engine() -> ToolEngine:
    global _tool_engine
    if _tool_engine is None:
        _tool_engine = ToolEngine()
    return _tool_engine
