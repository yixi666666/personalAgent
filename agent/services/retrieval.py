"""Fact 召回服务：双路召回 + RRF 融合。

流程（按全链路流程文档）：
1. 对每所 confirmed 高校，按 university_id 分 namespace
2. 每个 query 做双路召回：
   - 向量路：query embedding 与 facts_vec 余弦相似度
   - 关键词路：facts_fts BM25
3. 对两路召回结果做倒数排名融合（RRF, k=60）
4. 同一 fact 在多路命中时得分叠加，去重后统一排序
5. 硬阈值截断：相似度低于 0.6 的直接丢弃
6. 按 top_k=8 截断
7. 合并多所高校的召回结果
"""

import json
import logging
from typing import Optional

from agent.database import get_db
from agent.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

# RRF 参数
_RRF_K = 60
# 每个 query 的 top_k
_TOP_K = 8
# 硬阈值（余弦相似度）
_HARD_THRESHOLD = 0.55
# BM25 召回数量
_BM25_LIMIT = 20
# 向量召回数量
_VEC_LIMIT = 20


class RetrievalService:
    """Fact 召回服务"""

    # ------------------------------------------------------------------
    # 向量路召回
    # ------------------------------------------------------------------

    def _vector_recall(self, query: str, university_id: str) -> list[dict]:
        """向量路召回：query embedding 与 facts_vec 余弦相似度

        返回: [{"fact_id", "score", "rank"}, ...]
        """
        db = get_db()

        embedding_service = get_embedding_service()
        query_vec = embedding_service.encode_one(query)
        vec_json = json.dumps(query_vec.tolist())

        # 在 facts_vec 中做 KNN 搜索，然后关联 facts 表过滤 university_id
        rows = db.execute(
            "SELECT fact_id, distance FROM facts_vec "
            "WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance",
            (vec_json, _VEC_LIMIT * 3),  # 多取一些，过滤 university_id 后可能不够
        ).fetchall()

        # 关联 facts 表过滤 university_id
        results = []
        for row in rows:
            fact_row = db.execute(
                "SELECT id, university_id, content, retrieval_text FROM facts WHERE id = ?",
                (row["fact_id"],),
            ).fetchone()
            if not fact_row or fact_row["university_id"] != university_id:
                continue
            # distance 是 L2 距离，归一化向量下 distance = 2 - 2*cos
            cos_sim = 1.0 - float(row["distance"]) / 2.0
            results.append({
                "fact_id": row["fact_id"],
                "content": fact_row["content"],
                "retrieval_text": fact_row["retrieval_text"],
                "score": cos_sim,
            })

        return results[:_VEC_LIMIT]

    # ------------------------------------------------------------------
    # 关键词路召回
    # ------------------------------------------------------------------

    def _keyword_recall(self, query: str, university_id: str) -> list[dict]:
        """关键词路召回：facts_fts BM25

        返回: [{"fact_id", "score", "rank"}, ...]
        """
        db = get_db()

        # 用 jieba 分词后的 query 做 FTS 搜索
        # facts_fts 的 content 字段已经用 jieba 分词后空格分隔存储
        # 搜索时也需要对 query 做分词，用 OR 连接保证召回率
        import jieba
        jieba.setLogLevel(logging.WARNING)
        tokens = jieba.lcut(query)
        # 过滤单字停用词，用 OR 连接
        meaningful_tokens = [t for t in tokens if len(t.strip()) > 1]
        if not meaningful_tokens:
            return []
        fts_query = " OR ".join(meaningful_tokens)

        rows = db.execute(
            "SELECT fact_id, rank FROM facts_fts "
            "WHERE facts_fts MATCH ? "
            "ORDER BY rank "
            f"LIMIT {_BM25_LIMIT * 3}",
            (fts_query,),
        ).fetchall()

        # 关联 facts 表过滤 university_id
        results = []
        for row in rows:
            fact_row = db.execute(
                "SELECT id, university_id, content, retrieval_text FROM facts WHERE id = ?",
                (row["fact_id"],),
            ).fetchone()
            if not fact_row or fact_row["university_id"] != university_id:
                continue
            # BM25 的 rank 是负值（SQLite FTS5 的 rank 越小越相关）
            # 转为正分数：score = -rank
            results.append({
                "fact_id": row["fact_id"],
                "content": fact_row["content"],
                "retrieval_text": fact_row["retrieval_text"],
                "score": -float(row["rank"]),
            })

        return results[:_BM25_LIMIT]

    # ------------------------------------------------------------------
    # RRF 融合
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_fusion(
        vec_results: list[dict],
        fts_results: list[dict],
    ) -> list[dict]:
        """倒数排名融合（RRF）

        同一 fact 在多路命中时得分叠加，去重后统一排序。
        """
        rrf_scores: dict[str, float] = {}
        fact_data: dict[str, dict] = {}

        # 向量路排名
        for rank, item in enumerate(vec_results):
            fact_id = item["fact_id"]
            rrf_score = 1.0 / (_RRF_K + rank + 1)
            rrf_scores[fact_id] = rrf_scores.get(fact_id, 0.0) + rrf_score
            if fact_id not in fact_data:
                fact_data[fact_id] = {"content": item["content"], "vec_score": item.get("score", 0.0), "fts_score": 0.0}

        # 关键词路排名
        for rank, item in enumerate(fts_results):
            fact_id = item["fact_id"]
            rrf_score = 1.0 / (_RRF_K + rank + 1)
            rrf_scores[fact_id] = rrf_scores.get(fact_id, 0.0) + rrf_score
            if fact_id not in fact_data:
                fact_data[fact_id] = {"content": item["content"], "vec_score": 0.0, "fts_score": item.get("score", 0.0)}
            else:
                fact_data[fact_id]["fts_score"] = item.get("score", 0.0)

        # 按融合分数排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda fid: rrf_scores[fid], reverse=True)

        results = []
        for fact_id in sorted_ids:
            data = fact_data[fact_id]
            results.append({
                "fact_id": fact_id,
                "content": data["content"],
                "rrf_score": rrf_scores[fact_id],
                "vec_score": data["vec_score"],
            })

        return results

    # ------------------------------------------------------------------
    # 单校召回
    # ------------------------------------------------------------------

    def _recall_for_university(
        self,
        university_name: str,
        university_id: str,
        queries: list[str],
    ) -> list[dict]:
        """对单所高校的多条 query 做召回，合并结果

        返回: [{"fact_id", "content", "topic", "subtopic", "rrf_score"}, ...]
        """
        all_facts: dict[str, dict] = {}

        for query in queries:
            # 双路召回
            vec_results = self._vector_recall(query, university_id)
            fts_results = self._keyword_recall(query, university_id)

            # RRF 融合
            fused = self._rrf_fusion(vec_results, fts_results)

            # 硬阈值截断（向量路分数低于阈值的丢弃）
            fused = [f for f in fused if f["vec_score"] >= _HARD_THRESHOLD]

            # top_k 截断
            fused = fused[:_TOP_K]

            # 合并到该高校的总结果
            for item in fused:
                fid = item["fact_id"]
                if fid not in all_facts:
                    all_facts[fid] = item
                else:
                    # 取 RRF 分数更高的
                    if item["rrf_score"] > all_facts[fid]["rrf_score"]:
                        all_facts[fid] = item

        # 按 rrf_score 降序
        results = sorted(all_facts.values(), key=lambda x: x["rrf_score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # 挂载节点信息补充
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_with_taxonomy(facts: list[dict]) -> list[dict]:
        """为每条 fact 补充挂载节点的 topic/subtopic 信息

        挂载到 subtopic 时，通过 parent_code 反查所属 topic
        """
        if not facts:
            return facts

        db = get_db()
        for fact in facts:
            fact_id = fact["fact_id"]
            mounts = db.execute(
                "SELECT t.code, t.title, t.node_type, t.parent_code "
                "FROM fact_mounts fm "
                "JOIN taxonomy t ON fm.node_code = t.code "
                "WHERE fm.fact_id = ?",
                (fact_id,),
            ).fetchall()

            topic_title = ""
            subtopic_title = ""
            for m in mounts:
                if m["node_type"] == "subtopic":
                    subtopic_title = m["title"]
                    # 通过 parent_code 反查父级 topic
                    if m["parent_code"]:
                        parent = db.execute(
                            "SELECT title FROM taxonomy WHERE code = ?",
                            (m["parent_code"],),
                        ).fetchone()
                        if parent:
                            topic_title = parent["title"]
                elif m["node_type"] == "topic":
                    topic_title = m["title"]

            fact["topic"] = topic_title
            fact["subtopic"] = subtopic_title

        return facts

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def recall(self, confirmed_universities: list[dict]) -> dict:
        """Fact 召回主入口

        输入:
            confirmed_universities: [{"name", "queries", "university_id"}, ...]

        输出:
            {
              "universities": [
                {
                  "name": "湖南工业大学",
                  "facts": [
                    {"fact_id", "content", "topic", "subtopic", "rrf_score"},
                    ...
                  ]
                }
              ],
              "target_universities": ["湖南工业大学", ...]
            }
        """
        results = []
        target_names = []

        for uni in confirmed_universities:
            name = uni["name"]
            university_id = uni.get("university_id")
            queries = uni.get("queries", [])

            if not university_id or not queries:
                continue

            facts = self._recall_for_university(name, university_id, queries)

            if not facts:
                continue

            # 补充 taxonomy 信息
            facts = self._enrich_with_taxonomy(facts)

            results.append({
                "name": name,
                "facts": facts,
            })
            target_names.append(name)

        return {
            "universities": results,
            "target_universities": target_names,
        }

    @staticmethod
    def format_recall_xml(recall_result: dict) -> str:
        """将召回结果格式化为 XML 标签文本，供聊天 Agent 阅读

        格式:
        <chunks>
        <university name="湖南工业大学">
        【topic】【subtopic（如有）】：content原文

        【topic】：content原文
        </university>
        </chunks>
        """
        uni_parts = []
        for uni in recall_result.get("universities", []):
            uni_name = uni.get("name", "")
            facts = uni.get("facts", [])
            if not facts:
                continue
            lines = [f'<university name="{uni_name}">']
            fact_lines = []
            for fact in facts:
                topic = fact.get("topic", "")
                subtopic = fact.get("subtopic", "")
                content = fact.get("content", "")
                if subtopic:
                    fact_lines.append(f"【{topic}】【{subtopic}】：{content}")
                else:
                    fact_lines.append(f"【{topic}】：{content}")
            lines.append("\n\n".join(fact_lines))
            lines.append("</university>")
            uni_parts.append("\n".join(lines))
        return "<chunks>\n" + "\n".join(uni_parts) + "\n</chunks>"


_retrieval_service: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service
