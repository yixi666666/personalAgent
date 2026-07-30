import json
import uuid
import logging
from typing import Optional, AsyncGenerator
from agent.services.llm_client import get_llm_client
from agent.services.context_engine import get_context_engine
from agent.services.session import get_session_manager
from agent.services.tool_manager import get_tool_manager
from agent.config import get_config

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


class _Control:
    """内部控制信号，用于工具循环传递 next_messages 等信息"""

    __slots__ = ("next_messages", "next_parent_id", "format_retry_count")

    def __init__(
        self,
        next_messages: Optional[list[dict]] = None,
        next_parent_id: Optional[str] = None,
        format_retry_count: int = 0,
    ):
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

        tool_manager = get_tool_manager()
        tool_schemas = await tool_manager.get_tool_schemas_for_llm()

        context_engine = get_context_engine()
        llm_messages = context_engine.build_messages(
            session_id=session_id, model=model, tool_schemas=tool_schemas,
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
        deep_thinking: bool = False,
    ) -> AsyncGenerator[dict, None]:
        """流式对话（迭代式工具调用循环）

        本地模型（Arch-Agent-3B）使用 stream=false + tools 非流式路径，
        其他模型使用 stream=true 流式路径。
        工具调用循环使用迭代而非递归，最多 MAX_TOOL_ROUNDS 轮。
        """
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        current_messages = messages
        current_parent_id = parent_id
        format_retry_count = 0

        for _round in range(MAX_TOOL_ROUNDS):
            round_num = _round + 1
            control = None

            gen = self._call_stream(
                messages=current_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                session_id=session_id,
                parent_id=current_parent_id,
                supports_tools=supports_tools,
                deep_thinking=deep_thinking,
                round_num=round_num,
                format_retry_count=format_retry_count,
            )

            async for item in gen:
                if isinstance(item, _Control):
                    control = item
                else:
                    yield item

            if control and control.next_messages is not None:
                current_messages = control.next_messages
                current_parent_id = control.next_parent_id
                format_retry_count = control.format_retry_count
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
        deep_thinking: bool = False,
        round_num: int = 1,
        format_retry_count: int = 0,
    ) -> AsyncGenerator[dict | _Control, None]:
        """流式调用LLM，实时 yield 事件，结束时 yield _Control 控制信号"""
        tools = None
        if supports_tools:
            tool_manager = get_tool_manager()
            tools = await tool_manager.get_tool_schemas_for_llm()

        llm_client = get_llm_client()
        full_content = ""
        full_reasoning = ""
        tool_calls_buffer = []
        usage_data = {}
        model_name = ""
        round_prefix = f"【第{round_num}轮】" if round_num == 1 else f"[第{round_num}轮]"

        async for chunk in llm_client.chat_stream(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            supports_tools=supports_tools,
            deep_thinking=deep_thinking,
            round_num=round_num,
        ):
            # 收集 usage 和 model
            if chunk.get("usage"):
                usage_data = chunk["usage"]
            if chunk.get("model"):
                model_name = chunk["model"]

            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")

            # 处理 DeepSeek 思考模式的 reasoning_content
            if delta.get("reasoning_content"):
                full_reasoning += delta["reasoning_content"]
                yield {"type": "reasoning_delta", "content": delta["reasoning_content"]}

            if delta.get("content"):
                full_content += delta["content"]
                yield {"type": "delta", "content": delta["content"]}

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
                # 记录模型返回日志（与非流式格式一致）
                complete_response = {
                    "choices": [{
                        "finish_reason": finish_reason,
                        "message": {"content": full_content, "role": "assistant"},
                    }],
                    "usage": usage_data,
                }
                if model_name:
                    complete_response["model"] = model_name
                if full_reasoning:
                    complete_response["choices"][0]["message"]["reasoning_content"] = full_reasoning
                if tool_calls_buffer:
                    complete_response["choices"][0]["message"]["tool_calls"] = tool_calls_buffer
                logger.debug(f"{round_prefix} 模型返回 <<< {json.dumps(complete_response, ensure_ascii=False)}")

                if finish_reason == "tool_calls" and tool_calls_buffer:
                    # 按文档流程：存储 assistant 消息 + message_contents(reasoning + tool_call) + tool_calls(pending)
                    session_manager = get_session_manager()
                    reasoning_metadata = (
                        self._build_reasoning_metadata(usage_data, finish_reason)
                        if full_reasoning else None
                    )
                    assistant_msg_id = session_manager.add_assistant_message_with_tool_calls(
                        session_id=session_id,
                        content=full_content or "",
                        tool_calls=tool_calls_buffer,
                        parent_id=parent_id,
                        reasoning_content=full_reasoning,
                        reasoning_metadata=reasoning_metadata,
                    )
                    yield {"type": "tool_calls", "tool_calls": tool_calls_buffer}

                    # 执行工具并更新 tool_calls 记录
                    next_messages, next_parent_id, tool_results_info = await self._execute_and_update_tool_calls(
                        tool_calls_buffer, session_id, assistant_msg_id, model,
                    )
                    yield {"type": "tool_results", "tool_results": tool_results_info}
                    yield _Control(next_messages=next_messages, next_parent_id=next_parent_id)
                    return

                # 正常结束 - 不支持原生FC的模型可能从文本中输出工具调用
                if full_content and not supports_tools:
                    extracted_calls, parse_errors = self._extract_and_validate_tool_calls(full_content)

                    if extracted_calls:
                        session_manager = get_session_manager()
                        assistant_msg_id = session_manager.add_assistant_message_with_tool_calls(
                            session_id=session_id,
                            content="",
                            tool_calls=extracted_calls,
                            parent_id=parent_id,
                        )
                        yield {"type": "content_replace", "content": ""}
                        yield {"type": "tool_calls", "tool_calls": extracted_calls}

                        next_messages, next_parent_id, tool_results_info = await self._execute_and_update_tool_calls(
                            extracted_calls, session_id, assistant_msg_id, model,
                        )
                        yield {"type": "tool_results", "tool_results": tool_results_info}
                        yield _Control(next_messages=next_messages, next_parent_id=next_parent_id)
                        return

                    elif parse_errors:
                        # 按文档：参数校验异常时，终止回答用户问题
                        logger.debug(f"[工具参数校验异常] model={model}, 模型输出={full_content}, 异常原因={'; '.join(parse_errors)}")
                        session_manager = get_session_manager()
                        assistant_msg = session_manager.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=full_content,
                            parent_id=parent_id,
                        )
                        error_feedback = "工具调用解析失败，请按 JSON 格式输出工具调用。错误详情：\n" + "\n".join(parse_errors)
                        session_manager.add_message(
                            session_id=session_id,
                            role="user",
                            content=error_feedback,
                            parent_id=assistant_msg.id,
                        )
                        yield {"type": "error", "error": error_feedback}

                        next_messages = await self._rebuild_context(session_id, model)
                        yield _Control(
                            next_messages=next_messages,
                            next_parent_id=assistant_msg.id,
                            format_retry_count=format_retry_count + 1,
                        )
                        return

                # 普通回复
                if full_content:
                    session_manager = get_session_manager()
                    reasoning_metadata = (
                        self._build_reasoning_metadata(usage_data, finish_reason)
                        if full_reasoning else None
                    )
                    session_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_content,
                        parent_id=parent_id,
                        reasoning_content=full_reasoning,
                        reasoning_metadata=reasoning_metadata,
                    )

                yield {"type": "finish", "finish_reason": finish_reason}
                return

        # 流正常结束但没有finish_reason
        complete_response = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": full_content, "role": "assistant"},
            }],
            "usage": usage_data,
        }
        if model_name:
            complete_response["model"] = model_name
        logger.debug(f"{round_prefix} 模型返回 <<< {json.dumps(complete_response, ensure_ascii=False)}")
        if full_content:
            session_manager = get_session_manager()
            reasoning_metadata = (
                self._build_reasoning_metadata(usage_data, "stop")
                if full_reasoning else None
            )
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=full_content,
                parent_id=parent_id,
                reasoning_content=full_reasoning,
                reasoning_metadata=reasoning_metadata,
            )
        yield {"type": "finish", "finish_reason": "stop"}

    # ------------------------------------------------------------------
    # 公共方法：工具执行与更新
    # ------------------------------------------------------------------

    async def _execute_and_update_tool_calls(
        self,
        tool_calls: list[dict],
        session_id: str,
        assistant_msg_id: str,
        model: str,
    ) -> tuple[list[dict], str, list[dict]]:
        """执行工具调用并更新 tool_calls 记录

        按文档流程：
        1. tool_calls 已在 add_assistant_message_with_tool_calls 中以 status=pending 创建
        2. 执行工具
        3. 更新 tool_calls 记录（status、result），使用 call_id + message_id 双条件定位
        4. 不存储 role='tool' 消息，工具结果仅存 tool_calls 表

        返回: (new_messages, assistant_msg_id, tool_results_events)
        """
        session_manager = get_session_manager()
        tool_manager = get_tool_manager()
        tool_results = await tool_manager.execute_tool_calls(tool_calls)

        tool_results_info = []
        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("function", {}).get("name", "unknown")
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

            # 更新 tool_calls 记录（使用 call_id + message_id 双条件定位）
            session_manager.update_tool_call(
                call_id=tool_call_id,
                message_id=assistant_msg_id,
                result=result_content,
                status=call_status,
                error_message=error_message,
            )

            tool_results_info.append({
                "id": tool_call_id,
                "name": tool_name,
                "result": result_content,
                "status": call_status,
            })

        # 重建上下文（从数据库加载，tool 消息从 tool_calls 表动态生成）
        new_messages = await self._rebuild_context(session_id, model)
        return new_messages, assistant_msg_id, tool_results_info

    async def _rebuild_context(
        self, session_id: str, model: str
    ) -> list[dict]:
        """重建LLM上下文（从数据库加载完整历史）"""
        tool_manager = get_tool_manager()
        tool_schemas = await tool_manager.get_tool_schemas_for_llm()

        context_engine = get_context_engine()
        return context_engine.build_messages(
            session_id=session_id, model=model, tool_schemas=tool_schemas,
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

    @staticmethod
    def _build_reasoning_metadata(usage_data: dict, finish_reason: str) -> dict:
        """从 usage 数据构造 reasoning 内容块的 metadata

        按 init.sql 说明：reasoning 存储 {"tokens": 256, "finish_reason": "stop"} 等模型输出详情
        - tokens 优先取 completion_tokens_details.reasoning_tokens，回退到 completion_tokens
        - finish_reason 为模型返回的结束原因
        """
        metadata: dict = {"finish_reason": finish_reason or "stop"}
        if usage_data:
            completion_tokens_details = usage_data.get("completion_tokens_details") or {}
            reasoning_tokens = completion_tokens_details.get("reasoning_tokens")
            if reasoning_tokens is not None:
                metadata["tokens"] = reasoning_tokens
            elif usage_data.get("completion_tokens") is not None:
                metadata["tokens"] = usage_data.get("completion_tokens")
        return metadata

    # ------------------------------------------------------------------
    # 文本工具调用提取与校验
    # ------------------------------------------------------------------

    def _extract_and_validate_tool_calls(self, text: str) -> tuple[list[dict], list[str]]:
        """从文本中提取工具调用并校验参数

        Args:
            text: 模型输出的文本，接受 {"tool_calls": [...]} 格式

        返回: (tool_calls, parse_errors)
        """
        import jsonschema as jschema
        from agent.services.tool_manager import get_tool_manager

        raw_calls = []
        errors = []

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
