import logging
from typing import Optional
from app.services.conversation import get_conversation_manager

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 20


def sanitize_messages(messages: list[dict]) -> list[dict]:
    sanitized = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content.strip():
            continue
        if sanitized and sanitized[-1]["role"] == role:
            sanitized[-1]["content"] += "\n" + content
        else:
            sanitized.append({"role": role, "content": content})
    if sanitized and sanitized[0]["role"] != "user":
        sanitized = sanitized[1:]
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
    ) -> list[dict]:
        if new_messages:
            all_messages = list(new_messages)
        elif conversation_id:
            context = self.get_context(conversation_id)
            all_messages = context["history"]
        else:
            all_messages = []
        if len(all_messages) > MAX_CONTEXT_MESSAGES + 5:
            all_messages = all_messages[-(MAX_CONTEXT_MESSAGES + 5):]
        all_messages = sanitize_messages(all_messages)
        return all_messages

    def add_tool_result_to_context(
        self, context: dict, tool_name: str, tool_result: str
    ) -> dict:
        context["tool_results"].append(
            {"tool_name": tool_name, "result": tool_result}
        )
        return context


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
