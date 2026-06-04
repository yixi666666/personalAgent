import logging
from typing import Optional
from agent.services.conversation import get_conversation_manager

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 20

SYSTEM_PROMPT = (
    "你是一个智能助手，可以帮助用户解答问题。"
    "当需要获取实时信息或执行操作时，你可以使用提供的工具。"
    "请根据用户的问题选择合适的工具进行调用，然后基于工具返回的结果给出完整的回答。"
    "如果不需要工具即可回答，请直接回答用户的问题。"
)

TOOL_CALL_PROMPT_TEMPLATE = (
    "\n\n你可以使用以下工具来帮助回答问题：\n"
    "{tool_descriptions}\n"
    "当你需要调用工具时，请使用以下格式输出，每次调用一个工具：\n"
    "<tool_call>\n"
    '{{"name": "工具名", "arguments": {{参数}}}}\n'
    "</tool_call>\n"
    "如果需要调用多个工具，请分别输出多个 <tool_call> 块。\n"
    "如果不需要调用工具，请直接回答用户的问题。"
    "如果调用了工具，请基于工具返回的结果给出完整的回答。"
)


def sanitize_messages(messages: list[dict]) -> list[dict]:
    """清理消息列表，确保格式正确"""
    sanitized = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")
        if role == "tool":
            sanitized.append(msg)
            continue
        if content is None or (isinstance(content, str) and not content.strip()):
            if msg.get("tool_calls"):
                sanitized.append(msg)
            continue
        if sanitized and sanitized[-1]["role"] == role and role in ("user", "assistant"):
            if not sanitized[-1].get("tool_calls") and not msg.get("tool_calls"):
                prev_content = sanitized[-1].get("content", "")
                sanitized[-1]["content"] = prev_content + "\n" + (content if isinstance(content, str) else "")
                continue
        sanitized.append(msg)
    return sanitized


class ContextManager:
    def get_context(self, conversation_id: str) -> dict:
        conv_manager = get_conversation_manager()
        history = conv_manager.get_messages(conversation_id)
        if len(history) > MAX_CONTEXT_MESSAGES:
            history = history[-MAX_CONTEXT_MESSAGES:]
        return {
            "conversation_id": conversation_id,
            "history": history,
            "metadata": {},
            "tool_results": [],
        }

    def build_llm_messages(
        self,
        conversation_id: Optional[str],
        new_messages: list[dict],
        tool_schemas: Optional[list[dict]] = None,
        supports_tools: bool = True,
    ) -> list[dict]:
        """构建发送给LLM的消息列表，包含系统提示词和历史上下文"""
        system_content = SYSTEM_PROMPT
        if not supports_tools and tool_schemas:
            tool_descriptions = self._format_tool_descriptions(tool_schemas)
            system_content += TOOL_CALL_PROMPT_TEMPLATE.format(tool_descriptions=tool_descriptions)

        result = [{"role": "system", "content": system_content}]

        if conversation_id:
            context = self.get_context(conversation_id)
            history = context["history"]
            if len(history) > MAX_CONTEXT_MESSAGES:
                history = history[-MAX_CONTEXT_MESSAGES:]
            result.extend(history)

        if new_messages:
            result.extend(new_messages)

        if len(result) > MAX_CONTEXT_MESSAGES + 5:
            system_msg = result[0]
            result = [system_msg] + result[-(MAX_CONTEXT_MESSAGES + 4):]

        result = sanitize_messages(result)
        return result

    @staticmethod
    def _format_tool_descriptions(tool_schemas: list[dict]) -> str:
        """将工具schema格式化为文本描述"""
        descriptions = []
        for schema in tool_schemas:
            func = schema.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            param_str = ""
            if params and params.get("properties"):
                props = params["properties"]
                required = params.get("required", [])
                param_parts = []
                for pname, pinfo in props.items():
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    req = " (必填)" if pname in required else " (可选)"
                    param_parts.append(f"  - {pname}: {ptype}{req} - {pdesc}")
                param_str = "\n".join(param_parts)
            descriptions.append(f"- {name}: {desc}\n参数:\n{param_str}" if param_str else f"- {name}: {desc}")
        return "\n\n".join(descriptions)


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
