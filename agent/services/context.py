import json
import logging
import os
from typing import Optional
from agent.services.session import get_session_manager
from agent.config import get_config

logger = logging.getLogger(__name__)


def _load_prompt_file(filename: str) -> str:
    """从指定提示词文件加载内容"""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        filename,
    )
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"提示词文件未找到: {prompt_path}")
        return ""


# 预加载两套提示词
# Arch-Agent-3B -> system-prompt-local.txt（本地模型使用）
# xop3qwen1b7 -> system-prompt-standard.txt（星火模型使用）
LOCAL_SYSTEM_PROMPT = _load_prompt_file("system-prompt-local.txt") or "你是一个智能助手，可以帮助用户解答问题。"
STANDARD_SYSTEM_PROMPT = _load_prompt_file("system-prompt-standard.txt") or LOCAL_SYSTEM_PROMPT

# 模型名到提示词的映射
_MODEL_PROMPT_MAP = {
    "Arch-Agent-3B": LOCAL_SYSTEM_PROMPT,
    "xop3qwen1b7": STANDARD_SYSTEM_PROMPT,
}


def get_system_prompt(model: str = "") -> str:
    """根据模型名称返回对应的系统提示词"""
    return _MODEL_PROMPT_MAP.get(model, STANDARD_SYSTEM_PROMPT)


def sanitize_messages(messages: list[dict], supports_tools: bool = True) -> list[dict]:
    """清理消息列表，确保格式正确

    规则：
    - tool 消息始终保留（包含 tool_call_id 和 name）
    - supports_tools=True 时：assistant 的 tool_calls 保留
    - supports_tools=False 时：assistant 消息中的 tool_calls 移除，只保留 content
    - 空内容的 assistant 消息如果有 tool_calls 也保留（仅 supports_tools=True 时）
    - 合并连续的同角色消息
    """
    sanitized = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        # tool 消息始终保留，构建标准格式
        if role == "tool":
            tool_msg = {"role": "tool", "content": content or ""}
            if msg.get("tool_call_id"):
                tool_msg["tool_call_id"] = msg["tool_call_id"]
            if msg.get("name"):
                tool_msg["name"] = msg["name"]
            sanitized.append(tool_msg)
            continue

        # supports_tools=False 时，assistant 消息移除 tool_calls，只保留 content
        if not supports_tools and role == "assistant":
            clean_msg = {"role": "assistant", "content": content or ""}
            # 合并连续同角色的 assistant 消息
            if sanitized and sanitized[-1]["role"] == "assistant":
                prev_content = sanitized[-1].get("content", "")
                sanitized[-1]["content"] = prev_content + "\n" + (clean_msg["content"] if isinstance(clean_msg["content"], str) else "")
            else:
                sanitized.append(clean_msg)
            continue

        # 空内容但有 tool_calls 的 assistant 消息保留（仅 supports_tools=True）
        if content is None or (isinstance(content, str) and not content.strip()):
            if msg.get("tool_calls"):
                assistant_msg = {"role": "assistant", "content": None}
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = msg["tool_calls"]
                sanitized.append(assistant_msg)
            continue

        # 构建标准消息格式，移除 id/parent_id 等数据库字段
        clean_msg = {"role": role, "content": content}
        if role == "assistant" and msg.get("tool_calls"):
            clean_msg["tool_calls"] = msg["tool_calls"]

        # 合并连续同角色的 user/assistant 消息
        if sanitized and sanitized[-1]["role"] == role and role in ("user", "assistant"):
            if not sanitized[-1].get("tool_calls") and not msg.get("tool_calls"):
                prev_content = sanitized[-1].get("content", "")
                sanitized[-1]["content"] = prev_content + "\n" + (content if isinstance(content, str) else "")
                continue

        sanitized.append(clean_msg)
    return sanitized


class ContextManager:
    def get_context(self, session_id: str) -> dict:
        session_manager = get_session_manager()
        history = session_manager.get_messages(session_id)
        return {
            "session_id": session_id,
            "history": history,
            "metadata": {},
            "tool_results": [],
        }

    def build_llm_messages(
        self,
        session_id: Optional[str],
        new_messages: list[dict],
        tool_schemas: Optional[list[dict]] = None,
        supports_tools: bool = True,
        is_local: bool = False,
        model: str = "",
    ) -> list[dict]:
        """构建发送给LLM的消息列表，包含系统提示词和历史上下文"""
        system_content = get_system_prompt(model)
        if tool_schemas:
            if supports_tools:
                # 本地模型（supports_tools=True）：LLaMA-Factory 不会自动用 chat_template 渲染 tools 参数，
                # 需要在系统提示词中手动注入 chat_template 定义的格式指令和工具签名
                system_content += self._format_local_tool_instructions(tool_schemas)
            else:
                # 不支持原生 function calling 的模型：将工具描述嵌入系统提示词
                tool_descriptions = self._format_tool_descriptions(tool_schemas)
                system_content += f"\n{tool_descriptions}"

        result = [{"role": "system", "content": system_content}]

        if session_id:
            context = self.get_context(session_id)
            history = context["history"]
            result.extend(history)

        if new_messages:
            result.extend(new_messages)

        result = sanitize_messages(result, supports_tools=supports_tools)
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

    @staticmethod
    def _format_local_tool_instructions(tool_schemas: list[dict]) -> str:
        """按照 Arch-Agent-3B chat_template 规范，在系统提示词中注入工具格式指令

        完全对应 chat_template.jinja 中 tools 分支的渲染逻辑：
        - 工具签名放在 <tools></tools> XML 标签内
        - 格式指令要求使用 <tool_call 标签输出
        """
        tool_texts = []
        for schema in tool_schemas:
            tool_texts.append(json.dumps(schema, ensure_ascii=False))

        tools_block = "\n".join(tool_texts)

        return (
            f"\n\n# Tools\n\n"
            f"You may call one or more functions to assist with the user query.\n\n"
            f"You are provided with function signatures within <tools></tools> XML tags:\n"
            f"<tools>\n{tools_block}\n</tools>\n\n"
            f"For each function call, return a json object with function name and arguments "
            f"within <tool_call XML tags:\n"
            f'<tool_call\n{{"name": <function-name>, "arguments": <args-json-object>}}\n</tool_call'
        )


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
