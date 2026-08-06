import json
import logging
import os
from typing import Optional

import tiktoken

from agent.services.session import get_session_manager
from agent.config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------

_enc = None


def _get_encoder():
    global _enc
    if _enc is None:
        try:
            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            logger.warning("tiktoken 编码器加载失败，回退到 len(text)//3 估算")
            _enc = False
    return _enc


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    enc = _get_encoder()
    if enc is False:
        return len(text) // 3
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# sanitize_messages — 从 context.py 迁移，新增 reasoning_content 保留
# ---------------------------------------------------------------------------


def _merge_content(prev: str, new: str) -> str:
    prev_str = prev if isinstance(prev, str) else ""
    new_str = new if isinstance(new, str) else ""
    return prev_str + "\n" + new_str


def sanitize_messages(
    messages: list[dict], supports_tools: bool = True
) -> list[dict]:
    """清理消息列表，确保格式正确

    规则：
    - tool 消息始终保留（包含 tool_call_id 和 name）
    - supports_tools=True 时：assistant 的 tool_calls 保留
    - supports_tools=False 时：assistant 消息中的 tool_calls 移除，只保留 content
    - 空内容的 assistant 消息如果有 tool_calls 也保留（仅 supports_tools=True 时）
    - 合并连续的同角色消息
    - reasoning_content 字段保留（DeepSeek 工具调用循环需要）
    """
    sanitized = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")
        reasoning = msg.get("reasoning_content")

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
            clean_msg: dict = {"role": "assistant", "content": content or ""}
            if reasoning:
                clean_msg["reasoning_content"] = reasoning
            # 合并连续同角色的 assistant 消息
            if sanitized and sanitized[-1]["role"] == "assistant":
                prev_content = sanitized[-1].get("content", "")
                sanitized[-1]["content"] = _merge_content(prev_content, clean_msg["content"])
                if reasoning and sanitized[-1].get("reasoning_content"):
                    sanitized[-1]["reasoning_content"] = (
                        sanitized[-1]["reasoning_content"] + "\n" + reasoning
                    )
                elif reasoning:
                    sanitized[-1]["reasoning_content"] = reasoning
            else:
                sanitized.append(clean_msg)
            continue

        # 空内容但有 tool_calls 的 assistant 消息保留（仅 supports_tools=True）
        if content is None or (isinstance(content, str) and not content.strip()):
            if msg.get("tool_calls"):
                assistant_msg = {"role": "assistant", "content": None}
                assistant_msg["tool_calls"] = msg["tool_calls"]
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                sanitized.append(assistant_msg)
            continue

        # 构建标准消息格式，移除 id/parent_id 等数据库字段
        clean_msg = {"role": role, "content": content}
        if role == "assistant" and msg.get("tool_calls"):
            clean_msg["tool_calls"] = msg["tool_calls"]
        if role == "assistant" and reasoning:
            clean_msg["reasoning_content"] = reasoning

        # 合并连续同角色的 user/assistant 消息
        if sanitized and sanitized[-1]["role"] == role and role in ("user", "assistant"):
            if not sanitized[-1].get("tool_calls") and not msg.get("tool_calls"):
                prev_content = sanitized[-1].get("content", "")
                sanitized[-1]["content"] = _merge_content(prev_content, content)
                if role == "assistant" and reasoning:
                    if sanitized[-1].get("reasoning_content"):
                        sanitized[-1]["reasoning_content"] = (
                            sanitized[-1]["reasoning_content"] + "\n" + reasoning
                        )
                    else:
                        sanitized[-1]["reasoning_content"] = reasoning
                continue

        sanitized.append(clean_msg)
    return sanitized


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
)


class PromptBuilder:
    """根据模型能力动态构建系统提示词"""

    @staticmethod
    def _load_prompt(filename: str) -> str:
        prompt_path = os.path.join(_PROMPTS_DIR, filename)
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"提示词文件未找到: {prompt_path}")
            return ""

    def build(
        self,
        provider: dict,
        tool_schemas: list[dict] | None,
    ) -> str:
        from agent.services.skill_manager import get_skill_manager

        parts = [self._load_prompt("system-prompt-base.txt")]

        # 注入 skill 元信息（仅当 skills 非空时）
        skills_meta = get_skill_manager().get_skills_meta()
        if skills_meta:
            skills_format = self._load_prompt("skills-format.txt")
            available_skills_xml = self._render_available_skills(skills_meta)
            parts.append(skills_format)
            parts.append(available_skills_xml)

        # 注入 tool-call-format（仅当 supports_tools=False 且有工具时）
        if tool_schemas:
            supports_tools = provider.get("supports_tools", True)
            if not supports_tools:
                tool_format = self._load_prompt("tool-call-format.txt")
                tool_desc = self._format_tool_descriptions(tool_schemas)
                parts.append(tool_format)
                parts.append(f"你可以借助以下工具来协助回答用户问题：\n{tool_desc}")

        return "\n\n".join(parts)

    @staticmethod
    def _render_available_skills(skills_meta: list[dict]) -> str:
        """渲染 <available_skills> XML 标签"""
        items = []
        for skill in skills_meta:
            name = skill.get("name", "")
            desc = skill.get("description", "")
            items.append(
                f"  <skill>\n"
                f"    <name>{name}</name>\n"
                f"    <description>{desc}</description>\n"
                f"  </skill>"
            )
        return "<available_skills>\n" + "\n".join(items) + "\n</available_skills>"

    @staticmethod
    def _format_tool_descriptions(tool_schemas: list[dict]) -> str:
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
            descriptions.append(
                f"- {name}: {desc}\n参数:\n{param_str}" if param_str else f"- {name}: {desc}"
            )
        return "\n\n".join(descriptions)


# ---------------------------------------------------------------------------
# TokenBudget
# ---------------------------------------------------------------------------


class TokenBudget:
    OUTPUT_RESERVE_RATIO = 0.3
    OUTPUT_RESERVE_MAX = 4096
    MIN_HISTORY_BUDGET = 1024

    def calculate(self, provider: dict, system_tokens: int) -> int:
        context_window = provider.get("context_window", 4096)
        output_reserve = min(
            int(context_window * self.OUTPUT_RESERVE_RATIO),
            self.OUTPUT_RESERVE_MAX,
        )
        budget = context_window - output_reserve - system_tokens
        return max(budget, self.MIN_HISTORY_BUDGET)


# ---------------------------------------------------------------------------
# HistoryManager
# ---------------------------------------------------------------------------


class HistoryManager:
    """加载、裁剪、压缩历史消息"""

    @staticmethod
    def _group_messages(messages: list[dict]) -> list[list[dict]]:
        groups = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                group = [msg]
                i += 1
                while i < len(messages) and messages[i]["role"] == "tool":
                    group.append(messages[i])
                    i += 1
                groups.append(group)
            else:
                groups.append([msg])
                i += 1
        return groups

    @staticmethod
    def _group_tokens(group: list[dict]) -> int:
        total = 0
        for m in group:
            total += estimate_tokens(m.get("content"))
            total += estimate_tokens(m.get("reasoning_content"))
            if m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    func = tc.get("function", {})
                    total += estimate_tokens(func.get("arguments"))
                    total += estimate_tokens(func.get("name"))
        return total

    def get(self, session_id: str, token_budget: int) -> list[dict]:
        session_manager = get_session_manager()
        raw_messages = session_manager.get_messages(session_id)
        groups = self._group_messages(raw_messages)

        # 从尾部向前逐组累加 token
        selected_groups: list[list[dict]] = []
        accumulated_tokens = 0
        for group in reversed(groups):
            group_tokens = self._group_tokens(group)
            if accumulated_tokens + group_tokens > token_budget and len(selected_groups) >= 2:
                break
            selected_groups.insert(0, group)
            accumulated_tokens += group_tokens

        # 摘要压缩：最近 3 组不压缩，更早的组压缩
        keep_recent = 3
        if len(selected_groups) > keep_recent:
            for i in range(len(selected_groups) - keep_recent):
                selected_groups[i] = self._compress_group(selected_groups[i])

        return [msg for group in selected_groups for msg in group]

    @staticmethod
    def _compress_group(group: list[dict]) -> list[dict]:
        compressed = []
        for msg in group:
            if msg["role"] == "tool":
                content = msg.get("content", "")
                tool_name = msg.get("name", "")
                msg = dict(msg)
                msg["content"] = HistoryManager._compress_tool_result(tool_name, content)
                compressed.append(msg)
            elif msg["role"] == "assistant":
                msg = dict(msg)
                # 预算紧张时优先丢弃 reasoning
                msg.pop("reasoning_content", None)
                compressed.append(msg)
            else:
                compressed.append(msg)
        return compressed

    @staticmethod
    def _compress_tool_result(tool_name: str, content: str, max_chars: int = 400) -> str:
        try:
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0:
                count = len(data)
                first = json.dumps(data[0], ensure_ascii=False)[:max_chars]
                return f"[{tool_name}] 返回{count}条结果，首条: {first}...[已压缩]"
            elif isinstance(data, dict):
                summary = json.dumps(data, ensure_ascii=False)[:max_chars]
                return f"[{tool_name}] {summary}...[已压缩]"
            else:
                return f"[{tool_name}] {str(data)[:max_chars]}...[已压缩]"
        except (json.JSONDecodeError, TypeError):
            return f"[{tool_name}] {content[:max_chars]}...[已压缩]"


# ---------------------------------------------------------------------------
# ContextEngine
# ---------------------------------------------------------------------------


class ContextEngine:
    """上下文引擎：统一构建发送给 LLM 的消息列表"""

    def __init__(self):
        self._prompt_builder = PromptBuilder()
        self._history_manager = HistoryManager()
        self._token_budget = TokenBudget()

    def build_messages(
        self,
        session_id: str | None,
        model: str,
        tool_schemas: list[dict] | None = None,
    ) -> list[dict]:
        config = get_config()
        provider = config.resolve_model_provider(model)
        supports_tools = provider.get("supports_tools", True)

        # 1. 构建系统提示词
        system_prompt = self._prompt_builder.build(provider, tool_schemas)
        system_tokens = estimate_tokens(system_prompt)

        context_window = provider.get("context_window", 4096)
        if system_tokens > context_window * 0.8:
            logger.warning(
                f"系统提示词 token({system_tokens})超过 context_window({context_window})的80%"
            )

        # 2. 计算历史预算
        history_budget = self._token_budget.calculate(provider, system_tokens)

        # 3. 加载并裁剪历史
        history: list[dict] = []
        if session_id:
            history = self._history_manager.get(session_id, history_budget)

        # 4. 组装消息列表
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # 5. 清洗
        return sanitize_messages(messages, supports_tools=supports_tools)


_context_engine: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextEngine()
    return _context_engine
