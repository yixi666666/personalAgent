"""查询理解前置步骤：高校识别 + 需求拆解。

流程：
1. 文本模糊匹配：用户问题与 universities 表 name/aliases 做 LIKE 子串匹配
2. 语义匹配：用户问题 embedding 与 universities_vec 做余弦相似度召回
3. 合并候选 → 组装 reference 交给 LLM 查询理解 Agent
4. LLM 输出 confirmed/suspicious 高校列表 + 信息需求维度 requirements
5. 别名归一化：LLM 输出的 name 与库表全表 name+aliases 匹配，统一为官方全称
"""

import json
import logging
import os
from typing import Optional

import numpy as np

from agent.config import get_config
from agent.database import get_db
from agent.services.embedding_service import get_embedding_service
from agent.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
)

# 语义匹配召回数量
_SEMANTIC_TOP_K = 10
# 模糊匹配最大返回数
_FUZZY_LIMIT = 20


def _load_prompt(filename: str) -> str:
    path = os.path.join(_PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


class QueryUnderstandingService:
    """高校识别 + 问题改写前置步骤"""

    def __init__(self):
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _load_prompt("查询理解agent系统提示词.md")
        return self._system_prompt

    # ------------------------------------------------------------------
    # 候选召回
    # ------------------------------------------------------------------

    def _fuzzy_match(self, user_query: str) -> list[dict]:
        """文本模糊匹配：name 和 aliases 的 LIKE 子串匹配

        返回: [{"id", "name", "aliases"}, ...]
        """
        db = get_db()
        # 提取查询中的中文关键词做子串匹配
        # 对 name 做 LIKE，对 aliases 做 LIKE
        # 同时也对用户问题做子串包含 name 的匹配
        keywords = self._extract_keywords(user_query)
        if not keywords:
            return []

        conditions = []
        params = []
        for kw in keywords:
            conditions.append("name LIKE ?")
            params.append(f"%{kw}%")
            conditions.append("aliases LIKE ?")
            params.append(f"%{kw}%")

        sql = (
            "SELECT id, name, aliases FROM universities "
            f"WHERE {' OR '.join(conditions)} "
            f"LIMIT {_FUZZY_LIMIT}"
        )
        rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """从用户问题中提取可能的高校关键词

        简单策略：提取 2~6 字的中文连续片段，以及英文单词
        """
        import re

        keywords = []
        # 中文连续片段
        for m in re.finditer(r"[\u4e00-\u9fff]{2,6}", text):
            keywords.append(m.group())
        # 英文词
        for m in re.finditer(r"[A-Za-z]{2,}", text):
            keywords.append(m.group())

        return keywords

    def _semantic_match(self, user_query: str) -> list[dict]:
        """语义匹配：用户问题 embedding 与 universities_vec 余弦相似度召回

        返回: [{"id", "name", "aliases", "score"}, ...]
        """
        db = get_db()

        # 编码用户问题
        embedding_service = get_embedding_service()
        query_vec = embedding_service.encode_one(user_query)
        vec_json = json.dumps(query_vec.tolist())

        # 在 universities_vec 中做 KNN 搜索
        rows = db.execute(
            "SELECT university_id, distance FROM universities_vec "
            f"WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (vec_json, _SEMANTIC_TOP_K),
        ).fetchall()

        if not rows:
            return []

        # 关联 universities 表获取 name 和 aliases
        results = []
        for row in rows:
            uni_row = db.execute(
                "SELECT id, name, aliases FROM universities WHERE id = ?",
                (row["university_id"],),
            ).fetchone()
            if uni_row:
                # distance 是 L2 距离，转为相似度分数
                score = 1.0 - float(row["distance"])
                results.append({
                    "id": uni_row["id"],
                    "name": uni_row["name"],
                    "aliases": uni_row["aliases"],
                    "score": score,
                })

        return results

    # ------------------------------------------------------------------
    # 候选合并与去重
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_candidates(
        fuzzy_results: list[dict],
        semantic_results: list[dict],
    ) -> list[dict]:
        """合并模糊匹配和语义匹配结果，去重"""
        seen_ids = set()
        merged = []

        # 先放模糊匹配（精确度更高）
        for item in fuzzy_results:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                merged.append(item)

        # 再放语义匹配
        for item in semantic_results:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                merged.append(item)

        return merged

    @staticmethod
    def _format_reference(candidates: list[dict]) -> str:
        """格式化参考列表：每行一所学校，格式 `官方全名 | 别名，别名，…`"""
        lines = []
        for item in candidates:
            name = item["name"]
            aliases_raw = item.get("aliases", "[]")
            try:
                aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
            except (json.JSONDecodeError, TypeError):
                aliases = []
            alias_str = "，".join(aliases) if aliases else ""
            if alias_str:
                lines.append(f"{name} | {alias_str}")
            else:
                lines.append(name)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 历史对话组装
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_history_messages(history: list[dict]) -> list[dict]:
        """从对话历史中提取纯文本对话，过滤掉 tool 消息、tool_calls、reasoning_content

        只保留 user 和 assistant 的纯文本 content，用于查询理解 Agent 的上下文。
        """
        filtered = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role not in ("user", "assistant"):
                continue
            if not content or not content.strip():
                continue
            # 跳过带 tool_calls 的 assistant 消息（前置召回的伪工具调用）
            if msg.get("tool_calls"):
                continue
            filtered.append({"role": role, "content": content})
        return filtered

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[dict]) -> dict:
        """调用查询理解 Agent LLM，返回解析后的 JSON

        每次调用的 HTTP 请求 body 完整日志打印
        """
        config = get_config()
        model = config.default_model
        provider = config.resolve_model_provider(model)

        llm_client = get_llm_client()

        # 构建请求参数
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": provider.get("max_tokens", 2048),
            "temperature": provider.get("temperature", 0.7),
            "stream": False,
        }

        response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            max_tokens=kwargs["max_tokens"],
            temperature=kwargs["temperature"],
            agent_name="查询理解Agent",
        )

        # 提取文本内容
        choices = response.get("choices", [])
        if not choices:
            logger.warning("[查询理解LLM] 返回无 choices")
            return {"universities": {"confirmed": [], "suspicious": []}}

        content = choices[0].get("message", {}).get("content", "")
        return self._parse_llm_output(content)

    @staticmethod
    def _parse_llm_output(content: str) -> dict:
        """解析 LLM 输出的 JSON，容错处理"""
        # 尝试直接解析
        try:
            result = json.loads(content)
            if "universities" in result:
                return result
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 代码块
        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                if "universities" in result:
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号包裹的 JSON
        brace_match = re.search(r"\{[\s\S]*\}", content)
        if brace_match:
            try:
                result = json.loads(brace_match.group(0))
                if "universities" in result:
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning(f"[查询理解LLM] 输出解析失败: {content[:200]}")
        return {"universities": {"confirmed": [], "suspicious": []}}

    # ------------------------------------------------------------------
    # 别名归一化
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_university_name(name: str, candidates: list[dict]) -> Optional[str]:
        """将 LLM 输出的学校名与候选列表中的官方全称匹配

        匹配策略：
        1. 完全匹配 name
        2. 完全匹配 aliases
        3. 模糊匹配（包含关系）
        """
        for item in candidates:
            if name == item["name"]:
                return item["name"]
            # 匹配别名
            aliases_raw = item.get("aliases", "[]")
            try:
                aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
            except (json.JSONDecodeError, TypeError):
                aliases = []
            if name in aliases:
                return item["name"]

        # 模糊匹配
        for item in candidates:
            if name in item["name"] or item["name"] in name:
                return item["name"]
            aliases_raw = item.get("aliases", "[]")
            try:
                aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
            except (json.JSONDecodeError, TypeError):
                aliases = []
            for alias in aliases:
                if name in alias or alias in name:
                    return item["name"]

        # 库表全量匹配
        db = get_db()
        row = db.execute(
            "SELECT name FROM universities WHERE name = ? LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            return row["name"]

        # aliases 全量匹配
        row = db.execute(
            "SELECT name FROM universities WHERE aliases LIKE ? LIMIT 1",
            (f'%"{name}"%',),
        ).fetchone()
        if row:
            return row["name"]

        return None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def understand(
        self,
        user_query: str,
        history: list[dict],
    ) -> dict:
        """查询理解主入口

        输入:
            user_query: 用户当前问题
            history: 对话历史（get_messages 格式）

        输出:
            {
              "confirmed": [{"name": "官方全名", "requirements": ["..."], "university_id": "..."}],
              "suspicious": [{"name": "...", "requirements": ["..."]}],
              "candidates": [{"id", "name", "aliases"}, ...]  # 候选学校原始数据
            }
        """
        logger.info(f"[用户原始问题] {user_query}")

        # 1. 文本模糊匹配
        fuzzy_results = self._fuzzy_match(user_query)
        logger.debug(
            f"[高校模糊匹配] {len(fuzzy_results)} 所 - "
            f"{[r['name'] for r in fuzzy_results]}"
        )

        # 2. 语义匹配
        semantic_results = self._semantic_match(user_query)
        logger.debug(
            f"[高校语义匹配] {len(semantic_results)} 所 - "
            f"{[r['name'] for r in semantic_results]}"
        )

        # 3. 合并候选
        candidates = self._merge_candidates(fuzzy_results, semantic_results)
        logger.debug(
            f"[高校候选合并] {len(candidates)} 所 - "
            f"{[r['name'] for r in candidates]}"
        )

        # 4. 组装 LLM 输入
        reference = self._format_reference(candidates)

        # 组装最新一轮用户消息
        latest_parts = [f"<question>\n{user_query}\n</question>"]
        if reference:
            latest_parts.append(f"<reference>\n{reference}\n</reference>")
        latest_message = "\n".join(latest_parts)

        # 组装完整对话：系统提示词 + 过滤后的历史对话 + 最新一轮
        llm_messages = [{"role": "system", "content": self._get_system_prompt()}]
        history_messages = self._filter_history_messages(history)
        llm_messages.extend(history_messages)
        llm_messages.append({"role": "user", "content": latest_message})

        # 5. 调用 LLM
        llm_result = await self._call_llm(llm_messages)

        # 6. 解析输出
        universities_data = llm_result.get("universities", {})
        confirmed_raw = universities_data.get("confirmed", [])
        suspicious_raw = universities_data.get("suspicious", [])

        # 7. 别名归一化
        confirmed = []
        for item in confirmed_raw:
            name = item.get("name", "")
            requirements = item.get("requirements", [])
            official_name = self._normalize_university_name(name, candidates)
            if official_name:
                # 获取 university_id
                db = get_db()
                row = db.execute(
                    "SELECT id FROM universities WHERE name = ? LIMIT 1",
                    (official_name,),
                ).fetchone()
                confirmed.append({
                    "name": official_name,
                    "requirements": requirements,
                    "university_id": row["id"] if row else None,
                })
            else:
                # 库表中未找到，降级为 suspicious
                suspicious_raw.append(item)

        suspicious = []
        for item in suspicious_raw:
            name = item.get("name", "")
            requirements = item.get("requirements", [])
            suspicious.append({
                "name": name,
                "requirements": requirements,
            })

        result = {
            "confirmed": confirmed,
            "suspicious": suspicious,
            "candidates": candidates,
        }

        logger.debug(
            f"[查询理解LLM] 输出: {json.dumps(llm_result, ensure_ascii=False)}"
        )
        return result


_query_understanding_service: Optional[QueryUnderstandingService] = None


def get_query_understanding_service() -> QueryUnderstandingService:
    global _query_understanding_service
    if _query_understanding_service is None:
        _query_understanding_service = QueryUnderstandingService()
    return _query_understanding_service
