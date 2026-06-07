import json
import re
import uuid
import logging
from typing import Optional, AsyncGenerator
from agent.services.llm_client import get_llm_client
from agent.services.context import get_context_manager
from agent.services.session import get_session_manager
from agent.services.tool_manager import get_tool_manager
from agent.config import get_config

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


class _CallResult:
    """单次LLM调用的结果，用于迭代式工具循环"""

    __slots__ = ("events", "next_messages", "next_parent_id", "format_retry_count")

    def __init__(
        self,
        events: list[dict],
        next_messages: Optional[list[dict]] = None,
        next_parent_id: Optional[str] = None,
        format_retry_count: int = 0,
    ):
        self.events = events
        self.next_messages = next_messages
        self.next_parent_id = next_parent_id
        self.format_retry_count = format_retry_count


class ChatService:
    """聊天服务：协调会话管理、上下文构建、LLM调用和工具执行"""

    async def prepare_session(
        self, session_id: Optional[str], prompt: str, model: str
    ) -> tuple[str, list[dict], str]:
        """准备会话：创建或获取会话，保存用户消息，构建LLM上下文

        返回: (session_id, llm_messages, user_msg_id)
        """
        session_manager = get_session_manager()

        if not session_id:
            session = session_manager.create_session()
            session_id = session["id"]

        if not session_manager.session_exists(session_id):
            raise ValueError(f"会话不存在: {session_id}")

        parent_id = session_manager.get_last_message_id(session_id)
        user_msg = session_manager.add_message(
            session_id=session_id,
            role="user",
            content=prompt,
            parent_id=parent_id,
        )

        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)
        is_local = provider.get("provider") == "local"

        context_manager = get_context_manager()
        tool_manager = get_tool_manager()
        tool_schemas = await tool_manager.get_tool_schemas_for_llm()

        llm_messages = context_manager.build_llm_messages(
            session_id=session_id,
            new_messages=[],
            tool_schemas=tool_schemas,
            supports_tools=supports_tools,
            is_local=is_local,
            model=model,
        )

        return session_id, llm_messages, user_msg.id

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: str = "",
        parent_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """流式对话（迭代式工具调用循环）

        本地模型（Arch-Agent-3B）使用 stream=false + tools 非流式路径，
        其他模型使用 stream=true 流式路径。
        工具调用循环使用迭代而非递归，最多 MAX_TOOL_ROUNDS 轮。
        """
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)
        is_local = provider.get("provider") == "local"

        current_messages = messages
        current_parent_id = parent_id
        format_retry_count = 0

        for _round in range(MAX_TOOL_ROUNDS):
            if is_local and supports_tools:
                result = await self._call_non_stream(
                    messages=current_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    session_id=session_id,
                    parent_id=current_parent_id,
                    supports_tools=supports_tools,
                    format_retry_count=format_retry_count,
                )
            else:
                result = await self._call_stream(
                    messages=current_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    session_id=session_id,
                    parent_id=current_parent_id,
                    supports_tools=supports_tools,
                )

            for event in result.events:
                yield event

            if result.next_messages is not None:
                current_messages = result.next_messages
                current_parent_id = result.next_parent_id
                format_retry_count = result.format_retry_count
                continue

            return

        yield {"type": "error", "error": f"工具调用超过最大轮次限制({MAX_TOOL_ROUNDS})"}
        yield {"type": "finish", "finish_reason": "stop"}

    # ------------------------------------------------------------------
    # 流式调用路径
    # ------------------------------------------------------------------

    async def _call_stream(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: str = "",
        parent_id: Optional[str] = None,
        supports_tools: bool = True,
    ) -> _CallResult:
        """流式调用LLM，返回事件列表和下一步信息"""
        tools = None
        if supports_tools:
            tool_manager = get_tool_manager()
            tools = await tool_manager.get_tool_schemas_for_llm()

        llm_client = get_llm_client()
        full_content = ""
        tool_calls_buffer = []
        events: list[dict] = []

        async for chunk in llm_client.chat_stream(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            supports_tools=supports_tools,
        ):
            # chunk 已是 SDK 解析后的 dict，无需 json.loads
            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")

            if delta.get("content"):
                full_content += delta["content"]
                events.append({"type": "delta", "content": delta["content"]})

            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    idx = tc.get("index", 0)
                    while len(tool_calls_buffer) <= idx:
                        tool_calls_buffer.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    if tc.get("id"):
                        tool_calls_buffer[idx]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        tool_calls_buffer[idx]["function"]["name"] += tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        tool_calls_buffer[idx]["function"]["arguments"] += tc["function"]["arguments"]

            if finish_reason:
                if finish_reason == "tool_calls" and tool_calls_buffer:
                    session_manager = get_session_manager()
                    assistant_msg = session_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_content or "",
                        parent_id=parent_id,
                    )
                    events.append({"type": "tool_calls", "tool_calls": tool_calls_buffer})

                    next_messages, next_parent_id, tool_results_info = await self._save_and_execute_tool_calls(
                        tool_calls_buffer, session_id, assistant_msg.id, model, supports_tools,
                    )
                    events.append({"type": "tool_results", "tool_results": tool_results_info})
                    return _CallResult(events=events, next_messages=next_messages, next_parent_id=next_parent_id)

                # 正常结束 - 不支持原生FC的模型可能从文本中输出工具调用
                if full_content and not supports_tools:
                    extracted_calls, parse_errors = self._extract_and_validate_tool_calls(full_content)

                    if extracted_calls:
                        session_manager = get_session_manager()
                        assistant_msg = session_manager.add_message(
                            session_id=session_id,
                            role="assistant",
                            content="",
                            parent_id=parent_id,
                        )
                        events.append({"type": "content_replace", "content": ""})
                        events.append({"type": "tool_calls", "tool_calls": extracted_calls})

                        next_messages, next_parent_id, tool_results_info = await self._save_and_execute_tool_calls(
                            extracted_calls, session_id, assistant_msg.id, model, supports_tools,
                        )
                        events.append({"type": "tool_results", "tool_results": tool_results_info})
                        return _CallResult(events=events, next_messages=next_messages, next_parent_id=next_parent_id)

                    elif parse_errors:
                        session_manager = get_session_manager()
                        assistant_msg = session_manager.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=full_content,
                            parent_id=parent_id,
                        )
                        error_feedback = "工具调用解析失败，请检查格式并修正：\n" + "\n".join(parse_errors)
                        session_manager.add_message(
                            session_id=session_id,
                            role="user",
                            content=error_feedback,
                            parent_id=assistant_msg.id,
                        )
                        events.append({"type": "error", "error": error_feedback})

                        next_messages = await self._rebuild_context(session_id, model, supports_tools)
                        return _CallResult(events=events, next_messages=next_messages, next_parent_id=assistant_msg.id)

                # 普通回复
                if full_content:
                    session_manager = get_session_manager()
                    session_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_content,
                        parent_id=parent_id,
                    )

                events.append({"type": "finish", "finish_reason": finish_reason})
                return _CallResult(events=events)

        # 流正常结束但没有finish_reason
        if full_content:
            session_manager = get_session_manager()
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=full_content,
                parent_id=parent_id,
            )
        events.append({"type": "finish", "finish_reason": "stop"})
        return _CallResult(events=events)

    # ------------------------------------------------------------------
    # 非流式调用路径（本地模型）
    # ------------------------------------------------------------------

    async def _call_non_stream(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: str = "",
        parent_id: Optional[str] = None,
        supports_tools: bool = True,
        format_retry_count: int = 0,
    ) -> _CallResult:
        """非流式调用LLM（用于本地模型 stream=false + tools）"""
        tool_manager = get_tool_manager()
        tools = await tool_manager.get_tool_schemas_for_llm()

        llm_client = get_llm_client()
        response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            supports_tools=supports_tools,
        )

        choices = response.get("choices", [])
        if not choices:
            return _CallResult(events=[{"type": "finish", "finish_reason": "stop"}])

        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        events: list[dict] = []

        # 原生 function calling 工具调用
        if finish_reason == "tool_calls" and tool_calls:
            session_manager = get_session_manager()
            assistant_msg = session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                parent_id=parent_id,
            )

            formatted_calls = self._format_tool_calls(tool_calls)

            if content:
                events.append({"type": "delta", "content": content})

            events.append({"type": "tool_calls", "tool_calls": formatted_calls})

            next_messages, next_parent_id, tool_results_info = await self._save_and_execute_tool_calls(
                formatted_calls, session_id, assistant_msg.id, model, supports_tools,
            )
            events.append({"type": "tool_results", "tool_results": tool_results_info})
            return _CallResult(events=events, next_messages=next_messages, next_parent_id=next_parent_id)

        # 普通回复 - 检查文本中是否包含工具调用
        if content:
            extracted_calls, parse_errors = self._extract_and_validate_tool_calls(
                content, model_type="local"
            )

            if extracted_calls:
                session_manager = get_session_manager()
                assistant_msg = session_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content="",
                    parent_id=parent_id,
                )
                events.append({"type": "content_replace", "content": ""})
                events.append({"type": "tool_calls", "tool_calls": extracted_calls})

                next_messages, next_parent_id, tool_results_info = await self._save_and_execute_tool_calls(
                    extracted_calls, session_id, assistant_msg.id, model, supports_tools,
                )
                events.append({"type": "tool_results", "tool_results": tool_results_info})
                return _CallResult(events=events, next_messages=next_messages, next_parent_id=next_parent_id)

            elif parse_errors:
                MAX_FORMAT_RETRIES = 2
                if format_retry_count >= MAX_FORMAT_RETRIES:
                    error_msg = "模型多次输出非规范工具调用格式，已停止重试。错误详情：" + "; ".join(parse_errors)
                    events.append({"type": "error", "error": error_msg})
                    events.append({"type": "finish", "finish_reason": "stop"})
                    return _CallResult(events=events)

                session_manager = get_session_manager()
                assistant_msg = session_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    parent_id=parent_id,
                )
                error_feedback = "工具调用格式不规范，请使用 <tool_call 标签格式。错误详情：" + "; ".join(parse_errors)
                session_manager.add_message(
                    session_id=session_id,
                    role="user",
                    content=error_feedback,
                    parent_id=assistant_msg.id,
                )
                events.append({"type": "error", "error": error_feedback})

                next_messages = await self._rebuild_context(session_id, model, supports_tools)
                return _CallResult(
                    events=events,
                    next_messages=next_messages,
                    next_parent_id=assistant_msg.id,
                    format_retry_count=format_retry_count + 1,
                )

            # 纯文本回复（无工具调用）
            events.append({"type": "delta", "content": content})
            session_manager = get_session_manager()
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                parent_id=parent_id,
            )

        events.append({"type": "finish", "finish_reason": finish_reason})
        return _CallResult(events=events)

    # ------------------------------------------------------------------
    # 公共方法：工具调用保存与执行
    # ------------------------------------------------------------------

    async def _save_and_execute_tool_calls(
        self,
        tool_calls: list[dict],
        session_id: str,
        assistant_msg_id: str,
        model: str,
        supports_tools: bool,
    ) -> tuple[list[dict], str, list[dict]]:
        """保存工具调用记录、执行工具、保存结果消息，返回重建的上下文

        返回: (new_messages, assistant_msg_id, tool_results_events)
        """
        session_manager = get_session_manager()
        tool_manager = get_tool_manager()
        tool_results = await tool_manager.execute_tool_calls(tool_calls)

        tool_results_info = []
        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("function", {}).get("name", "unknown")
            arguments_str = tc.get("function", {}).get("arguments", "{}")
            tool_call_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
            result_msg = tool_results[i] if i < len(tool_results) else {}
            result_content = result_msg.get("content", "")

            # 判断工具调用是否成功
            call_status = "success"
            error_message = None
            try:
                result_obj = json.loads(result_content)
                if isinstance(result_obj, dict) and result_obj.get("code") and result_obj["code"] != "success":
                    call_status = "error"
                    error_message = result_obj.get("message", "")
            except (json.JSONDecodeError, KeyError):
                pass

            session_manager.save_tool_call(
                message_id=assistant_msg_id,
                tool_name=tool_name,
                parameters=arguments_str,
                result=result_content,
                status=call_status,
                error_message=error_message,
                call_id=tool_call_id,
            )

            session_manager.add_message(
                session_id=session_id,
                role="tool",
                content=result_content,
                parent_id=assistant_msg_id,
            )

            tool_results_info.append({
                "id": tool_call_id,
                "name": tool_name,
                "result": result_content,
                "status": call_status,
            })

        # 重建上下文
        new_messages = await self._rebuild_context(session_id, model, supports_tools)
        return new_messages, assistant_msg_id, tool_results_info

    async def _rebuild_context(
        self, session_id: str, model: str, supports_tools: bool
    ) -> list[dict]:
        """重建LLM上下文（从数据库加载完整历史）"""
        config = get_config()
        provider = config.resolve_model_provider(model)
        is_local = provider.get("provider") == "local"

        context_manager = get_context_manager()
        tool_schemas = None
        if supports_tools:
            tool_manager = get_tool_manager()
            tool_schemas = await tool_manager.get_tool_schemas_for_llm()

        return context_manager.build_llm_messages(
            session_id=session_id,
            new_messages=[],
            tool_schemas=tool_schemas,
            supports_tools=supports_tools,
            is_local=is_local,
            model=model,
        )

    # ------------------------------------------------------------------
    # 工具调用格式化
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tool_calls(tool_calls: list[dict]) -> list[dict]:
        """将非流式响应中的 tool_calls 转为标准格式"""
        formatted = []
        for tc in tool_calls:
            func = tc.get("function", {})
            arguments = func.get("arguments", "{}")
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            formatted.append({
                "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "arguments": arguments,
                },
            })
        return formatted

    # ------------------------------------------------------------------
    # 文本工具调用提取与校验
    # ------------------------------------------------------------------

    def _extract_and_validate_tool_calls(self, text: str, model_type: str = "standard") -> tuple[list[dict], list[str]]:
        """从文本中提取工具调用并校验参数

        Args:
            text: 模型输出的文本
            model_type: 模型类型
                - "local": 本地模型（Arch-Agent-3B），只接受 TOOL_TAG 规范格式
                - "standard": 星火模型等，接受 {"tool_calls": [...]} 格式

        返回: (tool_calls, parse_errors)
        """
        import jsonschema as jschema
        from agent.services.tool_manager import get_tool_manager

        raw_calls = []
        errors = []

        if model_type == "local":
            # 本地模型 Arch-Agent-3B：
            # - 通过 LLaMA-Factory OpenAI API 返回时，特殊 token 被解码为 <tool_call\n{...}\n<tool_call
            #   注意：闭合标签 </tool_call 也可能被解码为 <tool_call
            # - 原始 chat_template 格式为 <｜tool_call_begin｜>{...}<｜tool_call_end｜>
            # 两种格式都需要兼容
            patterns = [
                r'<tool_call\s*(\{.*?\})\s*</?tool_call',  # LLaMA-Factory 解码后的格式（兼容 <tool_call 和 </tool_call）
                r'\u003c\uff5ctool_call_begin\uff5c\u003e\s*(\{.*?\})\s*\u003c\uff5ctool_call_end\uff5c\u003e',  # 原始特殊 token 格式
                r'\u003c\uff5c\s*(\{.*?\})\s*\uff5c\u003e',  # 简化版 <｜{...}｜> 格式
            ]
            matches = []
            for p in patterns:
                matches = re.findall(p, text, re.DOTALL)
                if matches:
                    break
            if matches:
                for i, match in enumerate(matches):
                    try:
                        parsed = json.loads(match)
                        name = parsed.get("name", "")
                        arguments = parsed.get("arguments", {})
                        if isinstance(arguments, dict):
                            arguments = json.dumps(arguments, ensure_ascii=False)
                        raw_calls.append({
                            "id": f"call_{uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            },
                        })
                    except (json.JSONDecodeError, KeyError) as e:
                        errors.append(f"工具调用 #{i+1} JSON解析失败: {e}")
            else:
                # 文本中无标签，检测是否包含非规范工具调用意图
                non_standard_patterns = [
                    (r"Action:\s*\w+", "检测到非规范的 Action: 格式，本地模型只接受 <tool_call 格式"),
                    (r'"tool_calls"\s*:', "检测到非规范的 JSON tool_calls 格式，本地模型只接受 <tool_call 格式"),
                ]
                for pattern_str, error_msg in non_standard_patterns:
                    if re.search(pattern_str, text):
                        errors.append(error_msg)
                        break

        else:
            # 星火模型：接受 {"tool_calls": [...]} 格式
            tool_calls_idx = text.find('"tool_calls"')
            if tool_calls_idx != -1:
                start = text.rfind('{', 0, tool_calls_idx)
                if start != -1:
                    depth = 0
                    end = start
                    for i in range(start, len(text)):
                        if text[i] == '{':
                            depth += 1
                        elif text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    candidate = text[start:end]
                    try:
                        parsed = json.loads(candidate)
                        if "tool_calls" in parsed:
                            for tc in parsed.get("tool_calls", []):
                                call_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
                                func = tc.get("function", {})
                                name = func.get("name", "")
                                arguments = func.get("arguments", {})
                                if isinstance(arguments, dict):
                                    arguments = json.dumps(arguments, ensure_ascii=False)
                                raw_calls.append({
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": arguments,
                                    },
                                })
                    except (json.JSONDecodeError, KeyError) as e:
                        errors.append(f"JSON解析失败: {e}")

        if not raw_calls:
            return [], errors

        # 用 jsonschema 校验每个工具调用的参数
        tool_manager = get_tool_manager()
        validated_calls = []
        for tc in raw_calls:
            tool_name = tc.get("function", {}).get("name", "")
            arguments_str = tc.get("function", {}).get("arguments", "{}")

            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            except json.JSONDecodeError as e:
                errors.append(f"工具 '{tool_name}' 参数JSON解析失败: {e}")
                continue

            tool_info = tool_manager._tools.get(tool_name)
            if not tool_info:
                errors.append(f"未找到工具: {tool_name}")
                continue

            parameters_schema = tool_info.get("parameters", {})
            if parameters_schema:
                try:
                    jschema.validate(instance=arguments, schema=parameters_schema)
                except jschema.ValidationError as e:
                    errors.append(f"工具 '{tool_name}' 参数校验失败: {e.message}")
                    continue

            validated_calls.append(tc)

        return validated_calls, errors


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
