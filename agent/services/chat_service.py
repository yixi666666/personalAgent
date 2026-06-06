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


class ChatService:
    """聊天服务：协调会话管理、上下文构建、LLM调用和工具执行"""

    async def prepare_session(
        self, session_id: Optional[str], prompt: str, model: str
    ) -> tuple[str, list[dict], str]:
        """准备会话：创建或获取会话，保存用户消息，构建LLM上下文

        返回: (session_id, llm_messages, user_msg_id)
        """
        session_manager = get_session_manager()

        # 创建或获取会话
        if not session_id:
            session = session_manager.create_session()
            session_id = session["id"]

        if not session_manager.session_exists(session_id):
            raise ValueError(f"会话不存在: {session_id}")

        # 保存用户消息
        parent_id = session_manager.get_last_message_id(session_id)
        user_msg = session_manager.add_message(
            session_id=session_id,
            role="user",
            content=prompt,
            parent_id=parent_id,
        )

        # 获取模型配置
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)
        is_local = provider.get("provider") == "local"

        # 构建LLM消息
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
        """流式对话

        本地模型（Arch-Agent-3B）使用 stream=false + tools 非流式路径，
        其他模型使用 stream=true 流式路径。
        """
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)
        is_local = provider.get("provider") == "local"

        # 本地模型 + 支持tools → 使用 stream=false + tools 非流式路径
        if is_local and supports_tools:
            async for event in self._non_stream_chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                session_id=session_id,
                parent_id=parent_id,
            ):
                yield event
            return

        # 获取工具schema：supports_tools=True 时通过API传递tools
        # supports_tools=False 时工具描述嵌入系统提示词
        tools = None
        if supports_tools:
            tool_manager = get_tool_manager()
            tools = await tool_manager.get_tool_schemas_for_llm()

        # 调用LLM流式
        llm_client = get_llm_client()
        full_content = ""
        tool_calls_buffer = []

        async for chunk_str in llm_client.chat_stream(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            supports_tools=supports_tools,
        ):
            try:
                chunk = json.loads(chunk_str)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")

            # 处理增量内容
            if delta.get("content"):
                full_content += delta["content"]
                yield {"type": "delta", "content": delta["content"]}

            # 处理工具调用增量
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

            # 流结束
            if finish_reason:
                if finish_reason == "tool_calls" and tool_calls_buffer:
                    # 保存助手消息（工具调用）
                    session_manager = get_session_manager()
                    assistant_msg = session_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_content or "",
                        parent_id=parent_id,
                    )

                    yield {"type": "tool_calls", "tool_calls": tool_calls_buffer}

                    # 执行工具调用
                    tool_manager = get_tool_manager()
                    tool_results = await tool_manager.execute_tool_calls(tool_calls_buffer)

                    # 保存工具调用记录和工具结果消息
                    for i, tc in enumerate(tool_calls_buffer):
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

                        # 保存tool_call记录，使用LLM返回的原始tool_call id
                        session_manager.save_tool_call(
                            message_id=assistant_msg.id,
                            tool_name=tool_name,
                            parameters=arguments_str,
                            result=result_content,
                            status=call_status,
                            error_message=error_message,
                            call_id=tool_call_id,
                        )

                        # 保存tool结果消息
                        session_manager.add_message(
                            session_id=session_id,
                            role="tool",
                            content=result_content,
                            parent_id=assistant_msg.id,
                        )

                    # 构建新的上下文继续对话
                    config = get_config()
                    provider = config.resolve_model_provider(model)
                    supports_tools_new = provider.get("supports_tools", True)
                    is_local_new = provider.get("provider") == "local"

                    context_manager = get_context_manager()
                    new_tool_schemas = None
                    if supports_tools_new:
                        new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

                    new_messages = context_manager.build_llm_messages(
                        session_id=session_id,
                        new_messages=[],
                        tool_schemas=new_tool_schemas,
                        supports_tools=supports_tools_new,
                        is_local=is_local_new,
                        model=model,
                    )

                    # 递归流式调用
                    async for event in self.stream_chat(
                        messages=new_messages,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        session_id=session_id,
                        parent_id=assistant_msg.id,
                    ):
                        yield event
                    return

                # 正常结束 - 检查是否需要从文本中提取工具调用
                if full_content and not supports_tools:
                    extracted_calls, parse_errors = self._extract_and_validate_tool_calls(full_content)

                    if extracted_calls:
                        # 保存助手消息，保留原始内容（包含工具调用JSON的文本）
                        session_manager = get_session_manager()
                        assistant_msg = session_manager.add_message(
                            session_id=session_id,
                            role="assistant",
                            content=full_content,
                            parent_id=parent_id,
                        )

                        yield {"type": "content_replace", "content": ""}

                        yield {"type": "tool_calls", "tool_calls": extracted_calls}

                        # 执行工具调用
                        tool_manager = get_tool_manager()
                        tool_results = await tool_manager.execute_tool_calls(extracted_calls)

                        # 保存工具调用记录和工具结果消息
                        for i, tc in enumerate(extracted_calls):
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
                                message_id=assistant_msg.id,
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
                                parent_id=assistant_msg.id,
                            )

                        # 构建新的上下文继续对话
                        config = get_config()
                        provider = config.resolve_model_provider(model)
                        supports_tools_new = provider.get("supports_tools", True)
                        is_local_new = provider.get("provider") == "local"

                        context_manager = get_context_manager()
                        new_tool_schemas = None
                        if supports_tools_new:
                            new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

                        new_messages = context_manager.build_llm_messages(
                            session_id=session_id,
                            new_messages=[],
                            tool_schemas=new_tool_schemas,
                            supports_tools=supports_tools_new,
                            is_local=is_local_new,
                            model=model,
                        )

                        # 递归流式调用
                        async for event in self.stream_chat(
                            messages=new_messages,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            session_id=session_id,
                            parent_id=assistant_msg.id,
                        ):
                            yield event
                        return

                    elif parse_errors:
                        # 工具调用解析/校验失败，向模型反馈错误并请求修正
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

                        yield {"type": "error", "error": error_feedback}

                        # 构建新的上下文请求模型修正
                        config = get_config()
                        provider = config.resolve_model_provider(model)
                        supports_tools_new = provider.get("supports_tools", True)
                        is_local_new = provider.get("provider") == "local"

                        context_manager = get_context_manager()
                        new_tool_schemas = None
                        if supports_tools_new:
                            new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

                        new_messages = context_manager.build_llm_messages(
                            session_id=session_id,
                            new_messages=[],
                            tool_schemas=new_tool_schemas,
                            supports_tools=supports_tools_new,
                            is_local=is_local_new,
                            model=model,
                        )

                        async for event in self.stream_chat(
                            messages=new_messages,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            session_id=session_id,
                            parent_id=assistant_msg.id,
                        ):
                            yield event
                        return

                # 普通回复 - 保存助手消息
                if full_content:
                    session_manager = get_session_manager()
                    session_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_content,
                        parent_id=parent_id,
                    )

                yield {"type": "finish", "finish_reason": finish_reason}
                return

        # 如果流正常结束但没有finish_reason
        if full_content:
            session_manager = get_session_manager()
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=full_content,
                parent_id=parent_id,
            )
        yield {"type": "finish", "finish_reason": "stop"}

    async def _non_stream_chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        session_id: str = "",
        parent_id: Optional[str] = None,
        _format_retry_count: int = 0,
    ) -> AsyncGenerator[dict, None]:
        """非流式对话（用于本地模型 stream=false + tools）

        完全参照模型说明文档：Arch-Agent-3B 使用 stream=false + tools 参数调用，
        模型通过原生 function calling 返回结构化 tool_calls 字段。
        """
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        # 获取工具schema，通过API tools参数传递
        tool_manager = get_tool_manager()
        tools = await tool_manager.get_tool_schemas_for_llm()

        # 非流式调用
        llm_client = get_llm_client()
        response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            supports_tools=supports_tools,
        )

        # 解析非流式响应
        choices = response.get("choices", [])
        if not choices:
            yield {"type": "finish", "finish_reason": "stop"}
            return

        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        # 处理工具调用
        if finish_reason == "tool_calls" and tool_calls:
            # 保存助手消息（工具调用）
            session_manager = get_session_manager()
            assistant_msg = session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                parent_id=parent_id,
            )

            # 将tool_calls转为标准格式
            formatted_calls = []
            for tc in tool_calls:
                func = tc.get("function", {})
                arguments = func.get("arguments", "{}")
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                formatted_calls.append({
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "arguments": arguments,
                    },
                })

            # 如果有文本内容，先发送
            if content:
                yield {"type": "delta", "content": content}

            yield {"type": "tool_calls", "tool_calls": formatted_calls}

            # 执行工具调用
            tool_results = await tool_manager.execute_tool_calls(formatted_calls)

            # 保存工具调用记录和工具结果消息
            for i, tc in enumerate(formatted_calls):
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
                    message_id=assistant_msg.id,
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
                    parent_id=assistant_msg.id,
                )

            # 构建新的上下文继续对话
            context_manager = get_context_manager()
            new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

            new_messages = context_manager.build_llm_messages(
                session_id=session_id,
                new_messages=[],
                tool_schemas=new_tool_schemas,
                supports_tools=supports_tools,
                is_local=True,
                model=model,
            )

            # 递归调用（仍走非流式路径）
            async for event in self.stream_chat(
                messages=new_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                session_id=session_id,
                parent_id=assistant_msg.id,
            ):
                yield event
            return

        # 普通回复 - 检查文本中是否包含工具调用（模型可能未使用原生function calling）
        if content:
            # 本地模型只接受 <tool_call> 规范格式，其他格式视为错误
            extracted_calls, parse_errors = self._extract_and_validate_tool_calls(
                content, model_type="local"
            )

            if extracted_calls:
                # 保存助手消息，保留原始内容
                session_manager = get_session_manager()
                assistant_msg = session_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    parent_id=parent_id,
                )

                yield {"type": "content_replace", "content": ""}
                yield {"type": "tool_calls", "tool_calls": extracted_calls}

                # 执行工具调用
                tool_results = await tool_manager.execute_tool_calls(extracted_calls)

                # 保存工具调用记录和工具结果消息
                for i, tc in enumerate(extracted_calls):
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    arguments_str = tc.get("function", {}).get("arguments", "{}")
                    tool_call_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
                    result_msg = tool_results[i] if i < len(tool_results) else {}
                    result_content = result_msg.get("content", "")

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
                        message_id=assistant_msg.id,
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
                        parent_id=assistant_msg.id,
                    )

                # 构建新的上下文继续对话
                context_manager = get_context_manager()
                new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

                new_messages = context_manager.build_llm_messages(
                    session_id=session_id,
                    new_messages=[],
                    tool_schemas=new_tool_schemas,
                    supports_tools=supports_tools,
                    is_local=True,
                    model=model,
                )

                async for event in self.stream_chat(
                    messages=new_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    session_id=session_id,
                    parent_id=assistant_msg.id,
                ):
                    yield event
                return

            elif parse_errors:
                # 工具调用格式不规范，限制重试次数避免死循环
                MAX_FORMAT_RETRIES = 2
                if _format_retry_count >= MAX_FORMAT_RETRIES:
                    error_msg = "模型多次输出非规范工具调用格式，已停止重试。错误详情：" + "; ".join(parse_errors)
                    yield {"type": "error", "error": error_msg}
                    yield {"type": "finish", "finish_reason": "stop"}
                    return

                session_manager = get_session_manager()
                assistant_msg = session_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    parent_id=parent_id,
                )

                error_feedback = "工具调用格式不规范，请使用 <tool_call> 标签格式。错误详情：" + "; ".join(parse_errors)
                session_manager.add_message(
                    session_id=session_id,
                    role="user",
                    content=error_feedback,
                    parent_id=assistant_msg.id,
                )

                yield {"type": "error", "error": error_feedback}

                context_manager = get_context_manager()
                new_tool_schemas = await tool_manager.get_tool_schemas_for_llm()

                new_messages = context_manager.build_llm_messages(
                    session_id=session_id,
                    new_messages=[],
                    tool_schemas=new_tool_schemas,
                    supports_tools=supports_tools,
                    is_local=True,
                    model=model,
                )

                async for event in self._non_stream_chat(
                    messages=new_messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    session_id=session_id,
                    parent_id=assistant_msg.id,
                    _format_retry_count=_format_retry_count + 1,
                ):
                    yield event
                return

            # 纯文本回复（无工具调用）
            yield {"type": "delta", "content": content}
            session_manager = get_session_manager()
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
                parent_id=parent_id,
            )

        yield {"type": "finish", "finish_reason": finish_reason}

    def _extract_and_validate_tool_calls(self, text: str, model_type: str = "standard") -> tuple[list[dict], list[str]]:
        """从文本中提取工具调用并校验参数

        Args:
            text: 模型输出的文本
            model_type: 模型类型
                - "local": 本地模型（Arch-Agent-3B），只接受 <tool_call> 规范格式
                - "standard": 星火模型等，接受 {"tool_calls": [...]} 格式

        返回: (tool_calls, parse_errors)
        - tool_calls: 解析且校验通过的工具调用列表
        - parse_errors: 解析或校验失败的错误信息列表

        本地模型规范格式（唯一接受）：
        <tool_call>
        {"name": <function-name>, "arguments": <args-json-object>}
        </tool_call>

        星火模型格式：
        {"tool_calls": [...]}
        """
        import jsonschema as jschema
        from agent.services.tool_manager import get_tool_manager

        raw_calls = []
        errors = []

        if model_type == "local":
            # 本地模型：只接受 <tool_call>...</tool_call> 规范格式
            pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
            matches = re.findall(pattern, text, re.DOTALL)
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
                # 文本中无 <tool_call> 标签，检测是否包含非规范工具调用意图
                non_standard_patterns = [
                    (r'Action:\s*\w+', "检测到非规范的 Action: 格式，本地模型只接受 <tool_call> 规范格式"),
                    (r'"tool_calls"\s*:', "检测到非规范的 JSON tool_calls 格式，本地模型只接受 <tool_call> 规范格式"),
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
