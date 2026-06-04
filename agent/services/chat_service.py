import uuid
import json
import re
import logging
from typing import Optional, AsyncGenerator

from agent.services.conversation import get_conversation_manager
from agent.services.context import get_context_manager
from agent.services.tool_manager import get_tool_manager
from agent.services.llm_client import get_llm_client
from agent.config import get_config

logger = logging.getLogger(__name__)

MAX_TOOL_CALL_ROUNDS = 5


# ── 文本解析辅助函数 ──────────────────────────────────────────


def parse_tool_calls_from_text(text: str) -> list[dict] | None:
    """从模型输出的文本中解析工具调用JSON

    支持两种格式：
    1. JSON格式: {"tool_calls": [{"name": "...", "arguments": {...}}]}
    2. XML标签格式(Arch-Agent): <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    """
    tool_calls = []

    # 优先尝试 <tool_call> XML 标签格式（Arch-Agent-3B 等模型使用）
    xml_pattern = r'<tool_call>\s*(\{[\s\S]*?\})\s*</tool_call>'
    xml_matches = re.findall(xml_pattern, text)
    if xml_matches:
        for i, match_str in enumerate(xml_matches):
            try:
                data = json.loads(match_str)
                tool_calls.append({
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": data.get("name", ""),
                        "arguments": json.dumps(data.get("arguments", {}), ensure_ascii=False),
                    },
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析<tool_call>JSON失败: {e}")
        if tool_calls:
            return tool_calls

    # 回退到 JSON 格式匹配
    pattern = r'```json\s*(\{[\s\S]*?"tool_calls"[\s\S]*?\})\s*```'
    match = re.search(pattern, text)
    if not match:
        pattern2 = r'(\{"tool_calls"\s*:\s*\[[\s\S]*?\]})'
        match = re.search(pattern2, text)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        raw_calls = data.get("tool_calls", [])
        if not raw_calls:
            return None
        for i, call in enumerate(raw_calls):
            tool_calls.append({
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": call.get("name", ""),
                    "arguments": json.dumps(call.get("arguments", {}), ensure_ascii=False),
                },
            })
        return tool_calls
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"解析工具调用JSON失败: {e}")
        return None


def strip_tool_call_text(text: str) -> str:
    """从文本中移除工具调用JSON块，保留其余内容

    支持移除两种格式：
    1. JSON格式: {"tool_calls": [...]} 或 ```json ... ```
    2. XML标签格式: <tool_call>...</tool_call>
    """
    result = re.sub(r'<tool_call>\s*\{[\s\S]*?\}\s*</tool_call>', '', text)
    result = re.sub(r'```json\s*\{[\s\S]*?"tool_calls"[\s\S]*?\}\s*```', '', result)
    result = re.sub(r'\{"tool_calls"\s*:\s*\[[\s\S]*?\]}', '', result)
    return result.strip()


# ── ChatService ──────────────────────────────────────────────


class ChatService:
    """对话编排服务：协调 LLM、工具管理、上下文和会话管理"""

    def __init__(self):
        self._conv_manager = get_conversation_manager()
        self._ctx_manager = get_context_manager()
        self._tool_manager = get_tool_manager()
        self._llm_client = get_llm_client()
        self._config = get_config()

    # ── 公共接口 ────────────────────────────────────────────

    async def prepare_conversation(
        self,
        conversation_id: Optional[str],
        messages: list[dict],
        model: str,
    ) -> tuple[str, list[dict]]:
        """
        准备会话上下文：校验/创建会话，构建LLM消息列表。
        返回 (conversation_id, llm_messages)。
        """
        provider = self._config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        if conversation_id:
            if not self._conv_manager.conversation_exists(conversation_id):
                raise ValueError(f"会话不存在: {conversation_id}")
        else:
            conv = self._conv_manager.create_conversation()
            conversation_id = conv["conversation_id"]

        new_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") == "user"
        ]

        tool_schemas = await self._tool_manager.get_tool_schemas_for_llm()
        llm_messages = self._ctx_manager.build_llm_messages(
            conversation_id,
            new_messages,
            tool_schemas=tool_schemas if not supports_tools else None,
            supports_tools=supports_tools,
        )

        for msg in new_messages:
            self._conv_manager.add_message(conversation_id, msg["role"], msg["content"])

        return conversation_id, llm_messages

    async def chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: Optional[float] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """
        非流式对话：执行工具调用循环，返回最终结果。
        返回 {"content": str, "tool_calls": list, "usage": dict}
        """
        provider = self._config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        tool_schemas = await self._tool_manager.get_tool_schemas_for_llm()
        tools_param = tool_schemas if (tool_schemas and supports_tools) else None

        all_tool_call_records = []
        current_messages = list(messages)

        for round_num in range(MAX_TOOL_CALL_ROUNDS):
            try:
                llm_result = await self._llm_client.chat(
                    current_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools_param,
                )
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                raise

            choice = llm_result.get("choices", [{}])[0]
            assistant_message = choice.get("message", {})
            tool_calls = assistant_message.get("tool_calls")

            if not supports_tools and not tool_calls:
                content = assistant_message.get("content", "")
                parsed_calls = parse_tool_calls_from_text(content)
                if parsed_calls:
                    tool_calls = parsed_calls
                    assistant_message["content"] = strip_tool_call_text(content)
                else:
                    return {
                        "content": content,
                        "tool_calls": all_tool_call_records,
                        "usage": llm_result.get("usage", {}),
                    }

            if not tool_calls:
                # 保存助手最终回复到数据库
                if conversation_id:
                    self._conv_manager.add_message(conversation_id, "assistant", assistant_message.get("content", ""))
                return {
                    "content": assistant_message.get("content", ""),
                    "tool_calls": all_tool_call_records,
                    "usage": llm_result.get("usage", {}),
                }

            logger.info(f"第{round_num + 1}轮工具调用，共{len(tool_calls)}个工具调用")

            # 保存助手消息（含 tool_calls）到数据库
            if conversation_id:
                self._conv_manager.add_message(conversation_id, "assistant", assistant_message.get("content", ""))
            current_messages.append(assistant_message)
            tool_messages = await self._tool_manager.execute_tool_calls(tool_calls)

            if supports_tools:
                current_messages.extend(tool_messages)
                # 保存工具返回消息到数据库
                if conversation_id:
                    for tm in tool_messages:
                        self._conv_manager.add_message(conversation_id, tm["role"], tm["content"])
            else:
                # 不支持原生function calling的模型，使用 <tool_response> 标签包裹工具结果
                # 这符合 Arch-Agent-3B 等模型的 chat_template 格式
                tool_result_parts = []
                for tc, tm in zip(tool_calls, tool_messages):
                    tool_result_content = tm.get("content", "")
                    tool_result_parts.append(f"<tool_response>\n{tool_result_content}\n</tool_response>")
                tool_result_msg = {
                    "role": "user",
                    "content": "\n".join(tool_result_parts),
                }
                current_messages.append(tool_result_msg)
                # 保存工具返回消息到数据库
                if conversation_id:
                    self._conv_manager.add_message(conversation_id, tool_result_msg["role"], tool_result_msg["content"])

            self._record_tool_calls(tool_calls, tool_messages, all_tool_call_records, conversation_id)

        # 达到最大轮数后再调用一次LLM生成最终回复
        try:
            llm_result = await self._llm_client.chat(
                current_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            logger.error(f"最终LLM调用失败: {e}")
            raise

        choice = llm_result.get("choices", [{}])[0]
        final_content = choice.get("message", {}).get("content", "")
        # 保存最终回复到数据库
        if conversation_id:
            self._conv_manager.add_message(conversation_id, "assistant", final_content)
        return {
            "content": final_content,
            "tool_calls": all_tool_call_records,
            "usage": llm_result.get("usage", {}),
        }

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: Optional[float] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        流式对话生成器，yield 事件字典。
        事件类型：
          - {"type": "conversation_id", "conversation_id": str}
          - {"type": "delta", "content": str}
          - {"type": "tool_calls", "tool_calls": list}
          - {"type": "finish", "finish_reason": str}
          - {"type": "error", "error": str}
        """
        provider = self._config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        tool_schemas = await self._tool_manager.get_tool_schemas_for_llm()
        tools_param = tool_schemas if (tool_schemas and supports_tools) else None

        current_messages = list(messages)
        full_content = ""
        all_tool_call_records = []

        for round_num in range(MAX_TOOL_CALL_ROUNDS):
            try:
                assistant_message = {"role": "assistant", "content": ""}
                tool_calls_in_round = []

                if not supports_tools:
                    # 不支持function calling：实时流式输出，流结束后检测工具调用
                    try:
                        async for chunk_data in self._llm_client.chat_stream(
                            current_messages,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ):
                            try:
                                chunk = json.loads(chunk_data)
                                choice = chunk.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                delta_content = delta.get("content", "")

                                if delta_content:
                                    full_content += delta_content
                                    assistant_message["content"] += delta_content
                                    # 实时流式输出
                                    yield {"type": "delta", "content": delta_content}

                                # 检查流式结束
                                finish_reason = choice.get("finish_reason")
                                if finish_reason:
                                    break
                            except json.JSONDecodeError:
                                pass
                    except Exception as e:
                        error_msg = self._format_llm_error(e, model, provider)
                        yield {"type": "error", "error": f"模型调用失败: {error_msg}"}
                        yield {"type": "finish", "finish_reason": "stop"}
                        return

                    # 流结束后检测文本中的工具调用
                    parsed_calls = parse_tool_calls_from_text(full_content)
                    if parsed_calls:
                        tool_calls_in_round = parsed_calls
                        clean_content = strip_tool_call_text(full_content)
                        # 替换已流式输出的内容为清理后的版本（移除工具调用JSON）
                        yield {"type": "content_replace", "content": clean_content}
                    else:
                        # 无工具调用，内容已实时输出完毕
                        break
                else:
                    # 支持function calling：流式输出
                    try:
                        async for chunk_data in self._llm_client.chat_stream(
                            current_messages,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            tools=tools_param,
                        ):
                            try:
                                chunk = json.loads(chunk_data)
                                choice = chunk.get("choices", [{}])[0]

                                delta = choice.get("delta", {})
                                delta_content = delta.get("content", "")
                                delta_tool_calls = delta.get("tool_calls")

                                if delta_tool_calls:
                                    for dtc in delta_tool_calls:
                                        idx = dtc.get("index", 0)
                                        while len(tool_calls_in_round) <= idx:
                                            tool_calls_in_round.append({
                                                "id": "",
                                                "type": "function",
                                                "function": {"name": "", "arguments": ""},
                                            })
                                        tc = tool_calls_in_round[idx]
                                        if dtc.get("id"):
                                            tc["id"] = dtc["id"]
                                        if dtc.get("function", {}).get("name"):
                                            tc["function"]["name"] += dtc["function"]["name"]
                                        if dtc.get("function", {}).get("arguments"):
                                            tc["function"]["arguments"] += dtc["function"]["arguments"]

                                if delta_content:
                                    full_content += delta_content
                                    assistant_message["content"] += delta_content
                                    yield {"type": "delta", "content": delta_content}

                            except json.JSONDecodeError:
                                pass
                    except Exception as e:
                        error_msg = self._format_llm_error(e, model, provider)
                        yield {"type": "error", "error": f"模型调用失败: {error_msg}"}
                        yield {"type": "finish", "finish_reason": "stop"}
                        return

                    if not tool_calls_in_round:
                        break

                logger.info(f"流式第{round_num + 1}轮工具调用，共{len(tool_calls_in_round)}个工具调用")

                if assistant_message.get("content") or tool_calls_in_round:
                    # 对于不支持function calling的模型，保存/追加时需清理工具调用JSON
                    content_to_save = assistant_message.get("content", "")
                    if tool_calls_in_round and not supports_tools:
                        content_to_save = strip_tool_call_text(content_to_save) or None
                    msg_to_append = {"role": "assistant", "content": content_to_save}
                    if tool_calls_in_round and supports_tools:
                        msg_to_append["tool_calls"] = tool_calls_in_round
                    current_messages.append(msg_to_append)
                    # 保存助手消息到数据库
                    if conversation_id and content_to_save:
                        self._conv_manager.add_message(conversation_id, "assistant", content_to_save)

                tool_messages = await self._tool_manager.execute_tool_calls(tool_calls_in_round)
                self._record_tool_calls(tool_calls_in_round, tool_messages, all_tool_call_records, conversation_id)

                yield {"type": "tool_calls", "tool_calls": all_tool_call_records}

                if supports_tools:
                    current_messages.extend(tool_messages)
                    # 保存工具返回消息到数据库
                    if conversation_id:
                        for tm in tool_messages:
                            self._conv_manager.add_message(conversation_id, tm["role"], tm["content"])
                else:
                    # 不支持原生function calling的模型，使用 <tool_response> 标签包裹工具结果
                    tool_result_parts = []
                    for tc, tm in zip(tool_calls_in_round, tool_messages):
                        tool_result_content = tm.get("content", "")
                        tool_result_parts.append(f"<tool_response>\n{tool_result_content}\n</tool_response>")
                    tool_result_msg = {
                        "role": "user",
                        "content": "\n".join(tool_result_parts),
                    }
                    current_messages.append(tool_result_msg)
                    # 保存工具返回消息到数据库
                    if conversation_id:
                        self._conv_manager.add_message(conversation_id, tool_result_msg["role"], tool_result_msg["content"])

                full_content = ""

            except Exception as e:
                error_msg = self._format_llm_error(e, model, provider)
                yield {"type": "error", "error": f"对话处理失败: {error_msg}"}
                yield {"type": "finish", "finish_reason": "stop"}
                return

        self._conv_manager.add_message(conversation_id, "assistant", full_content)
        yield {"type": "finish", "finish_reason": "stop"}

    def save_assistant_message(self, conversation_id: str, content: str):
        """保存assistant消息到会话"""
        self._conv_manager.add_message(conversation_id, "assistant", content)

    # ── 内部辅助 ────────────────────────────────────────────

    def _record_tool_calls(
        self,
        tool_calls: list[dict],
        tool_messages: list[dict],
        all_records: list[dict],
        conversation_id: Optional[str],
    ):
        """记录工具调用结果到列表和会话存储"""
        for tc, tm in zip(tool_calls, tool_messages):
            tool_name = tc.get("function", {}).get("name", "unknown")
            tool_args_str = tc.get("function", {}).get("arguments", "{}")
            tool_result_content = tm.get("content", "")
            all_records.append({
                "tool_name": tool_name,
                "tool_args": tool_args_str,
                "result": tool_result_content,
            })
            if conversation_id:
                try:
                    self._conv_manager.save_tool_call(
                        conversation_id,
                        tool_name,
                        tool_args_str,
                        tool_result_content,
                    )
                except Exception as e:
                    logger.warning(f"保存工具调用记录失败: {e}")

    @staticmethod
    def _format_llm_error(error: Exception, model: str, provider: dict) -> str:
        """格式化LLM调用错误信息"""
        error_msg = str(error)
        if provider.get("provider") == "local":
            error_msg = f"本地模型 [{model}] 不可用，请确认模型服务是否已启动"
        return error_msg


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
