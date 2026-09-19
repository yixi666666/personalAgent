"""召回 Agent：迭代式 Fact 召回协调器。

流程：
1. 接收查询理解 Agent 的 confirmed 高校列表（含 requirements + university_id）
2. 第一轮：调用召回 LLM 生成 queries → 双路召回 → 得到 facts
3. 后续轮：将已召回 facts 反馈给召回 LLM，判断 sufficient 或生成新 queries
4. 最多 MAX_ROUNDS 轮，超过后强制停止
5. 每轮的 queries + 召回结果独立返回，由调用方逐条写入 DB tool_call

与 RetrievalService 的关系：
- RecallAgentService 负责"生成 queries + 判断 sufficient"的 LLM 逻辑
- RetrievalService 负责"双路召回 + RRF 融合"的检索逻辑
"""

import json
import logging
import os
from typing import Optional

from agent.config import get_config
from agent.services.llm_client import get_llm_client
from agent.services.retrieval import get_retrieval_service, RetrievalService

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts",
)

MAX_ROUNDS = 3


def _load_prompt(filename: str) -> str:
    path = os.path.join(_PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


class RecallAgentService:
    """召回 Agent：迭代式生成 queries、判断充足性、协调 RetrievalService 召回"""

    def __init__(self):
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _load_prompt("召回agent系统提示词.md")
        return self._system_prompt

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[dict], round_num: int = 1, model: str = "") -> dict:
        """调用召回 Agent LLM，返回解析后的 JSON"""
        config = get_config()
        if not model:
            model = config.default_model
        provider = config.resolve_model_provider(model)

        llm_client = get_llm_client()

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
            agent_name="召回Agent",
            round_num=round_num,
        )

        choices = response.get("choices", [])
        if not choices:
            logger.warning("[召回LLM] 返回无 choices")
            return {"sufficient": False, "universities": []}

        content = choices[0].get("message", {}).get("content", "")
        return self._parse_llm_output(content)

    @staticmethod
    def _parse_llm_output(content: str) -> dict:
        """解析 LLM 输出的 JSON，容错处理"""
        try:
            result = json.loads(content)
            if "sufficient" in result:
                return result
        except json.JSONDecodeError:
            pass

        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                if "sufficient" in result:
                    return result
            except json.JSONDecodeError:
                pass

        brace_match = re.search(r"\{[\s\S]*\}", content)
        if brace_match:
            try:
                result = json.loads(brace_match.group(0))
                if "sufficient" in result:
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning(f"[召回LLM] 输出解析失败: {content[:200]}")
        return {"sufficient": False, "universities": []}

    # ------------------------------------------------------------------
    # 输入组装
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_history_messages(history: list[dict]) -> list[dict]:
        """从对话历史中提取纯文本对话，过滤掉 tool 消息、tool_calls、reasoning_content

        只保留 user 和 assistant 的纯文本 content，用于召回 Agent 的上下文。
        """
        filtered = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role not in ("user", "assistant"):
                continue
            if not content or not content.strip():
                continue
            if msg.get("tool_calls"):
                continue
            filtered.append({"role": role, "content": content})
        return filtered

    @staticmethod
    def _build_fact_tool_messages(
        rounds_queries: list[dict[str, list[str]]],
        rounds_results: list[dict],
    ) -> list[dict]:
        """将之前各轮召回的 fact 伪装成 assistant tool_call + tool result 消息对

        每轮一条 tool_call，arguments 格式:
          {"universities": [{"name": "湖南工业大学", "queries": ["..."]}, ...]}
        tool result 格式:
          {"universities": [{"name": "...", "facts": [...]}], "target_universities": [...]}
        """
        messages = []
        for idx, (queries_by_uni, recall_result) in enumerate(zip(rounds_queries, rounds_results)):
            if not queries_by_uni:
                continue
            call_id = f"recall_prev_{idx}"
            # arguments: 每所高校的 name + queries 列表
            universities_args = [
                {"name": uni_name, "queries": queries}
                for uni_name, queries in queries_by_uni.items()
            ]
            tool_arguments = json.dumps(
                {"universities": universities_args}, ensure_ascii=False
            )
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "university_recall",
                        "arguments": tool_arguments,
                    },
                }],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": RetrievalService.format_recall_xml(recall_result),
            })
        return messages

    def _build_llm_messages(
        self,
        system_prompt: str,
        history: list[dict],
        confirmed: list[dict],
        prev_rounds_queries: list[dict[str, list[str]]],
        prev_rounds_results: list[dict],
    ) -> list[dict]:
        """组装召回 Agent 的完整 LLM 消息列表

        结构：系统提示词 + 过滤后的对话历史 + 之前各轮召回的 fact（伪装工具调用）+ 当前轮 requirements
        """
        llm_messages = [{"role": "system", "content": system_prompt}]

        # 对话历史（纯文本，过滤 tool/reasoning）
        llm_messages.extend(self._filter_history_messages(history))

        # 之前各轮召回的 fact（伪装成 assistant+tool 消息对）
        llm_messages.extend(self._build_fact_tool_messages(
            prev_rounds_queries, prev_rounds_results,
        ))

        # 当前轮 requirements 作为最新 user 消息
        universities_input = []
        for uni in confirmed:
            name = uni["name"]
            requirements = uni.get("requirements", [])
            universities_input.append({
                "name": name,
                "requirements": requirements,
            })

        user_content = (
            f"<universities>\n"
            f"{json.dumps(universities_input, ensure_ascii=False, indent=2)}\n"
            f"</universities>"
        )
        llm_messages.append({"role": "user", "content": user_content})

        return llm_messages

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def iterative_recall(
        self,
        user_query: str,
        confirmed: list[dict],
        history: list[dict],
        model: str = "",
    ):
        """迭代式召回主入口（async generator）

        每轮召回完成后立即 yield 结果，调用方可逐轮入库+推送，
        无需等待所有轮次结束。

        输入:
            user_query: 用户原始问题
            confirmed: 查询理解输出的 confirmed 列表
                [{"name", "requirements", "university_id"}, ...]
            history: 对话历史（get_messages 格式）

        yield 每轮结果:
            {
              "round": 1,
              "queries_by_uni": {"湖南工业大学": ["query1", ...], ...},
              "recall_result": {"universities": [...], "target_universities": [...]},
              "sufficient": false
            }
        """
        retrieval_service = get_retrieval_service()
        system_prompt = self._get_system_prompt()

        # 记录各轮的 queries 和 recall_result，用于后续轮次伪装 tool_call
        prev_rounds_queries: list[dict[str, list[str]]] = []
        prev_rounds_results: list[dict] = []

        for round_num in range(1, MAX_ROUNDS + 1):
            # 1. 组装 LLM 消息并调用
            llm_messages = self._build_llm_messages(
                system_prompt, history, confirmed,
                prev_rounds_queries, prev_rounds_results,
            )

            llm_result = await self._call_llm(llm_messages, round_num=round_num, model=model)
            sufficient = llm_result.get("sufficient", False)
            uni_outputs = llm_result.get("universities", [])

            # 2. 如果 sufficient=true，停止召回
            if sufficient:
                logger.info(f"[fact双路召回] 第{round_num}轮 sufficient=true，停止")
                yield {
                    "round": round_num,
                    "sufficient": True,
                    "queries_by_uni": {},
                    "recall_result": {"universities": [], "target_universities": []},
                }
                return

            # 3. 提取每所高校的 queries
            queries_by_uni: dict[str, list[str]] = {}
            for uni_out in uni_outputs:
                name = uni_out.get("name", "")
                queries = uni_out.get("queries", [])
                if name and queries:
                    queries_by_uni[name] = queries

            if not queries_by_uni:
                logger.info(f"[fact双路召回] 第{round_num}轮 无有效queries，停止")
                yield {
                    "round": round_num,
                    "sufficient": False,
                    "queries_by_uni": {},
                    "recall_result": {"universities": [], "target_universities": []},
                }
                return

            # 4. 组装 retrieval_service.recall() 的输入
            recall_input = []
            for uni in confirmed:
                name = uni["name"]
                queries = queries_by_uni.get(name, [])
                if queries:
                    recall_input.append({
                        "name": name,
                        "queries": queries,
                        "university_id": uni.get("university_id"),
                    })

            # 5. 执行双路召回
            recall_result = retrieval_service.recall(recall_input)

            # 6. 记录本轮 queries 和 results，供后续轮次伪装 tool_call
            prev_rounds_queries.append(queries_by_uni)
            prev_rounds_results.append(recall_result)

            # 7. 汇总日志：sufficient + 各校query列表 + 召回条数
            uni_parts = []
            for uni_name, uni_queries in queries_by_uni.items():
                facts_count = sum(
                    len(u.get("facts", []))
                    for u in recall_result.get("universities", [])
                    if u.get("name") == uni_name
                )
                uni_parts.append(f"{uni_name}: queries={uni_queries}, facts={facts_count}")
            total_facts = sum(len(u.get("facts", [])) for u in recall_result.get("universities", []))
            logger.info(
                f"[fact双路召回] 第{round_num}轮 sufficient=false, "
                f"共{total_facts}条 | {' | '.join(uni_parts)}"
            )

            yield {
                "round": round_num,
                "sufficient": False,
                "queries_by_uni": queries_by_uni,
                "recall_result": recall_result,
            }

            # 8. 如果是最后一轮，强制停止
            if round_num == MAX_ROUNDS:
                logger.info(f"[fact双路召回] 达到最大轮次({MAX_ROUNDS})，强制停止")


_recall_agent_service: Optional[RecallAgentService] = None


def get_recall_agent_service() -> RecallAgentService:
    global _recall_agent_service
    if _recall_agent_service is None:
        _recall_agent_service = RecallAgentService()
    return _recall_agent_service
