import logging
import httpx

logger = logging.getLogger(__name__)

RAGBASE_SEARCH_URL = "http://localhost:8004/v1/search"


class RagSearchTool:
    """自研工具：调用RagBase知识库检索接口，返回原始文档片段"""

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return "在知识库中检索与查询相关的文档片段。返回每条结果的content（文档内容）、source（来源文件名）和score（相似度分数，L2距离，越小越相似）。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询文本",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的最大结果数，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)

        try:
            response = httpx.post(
                RAGBASE_SEARCH_URL,
                json={"query": query, "top_k": top_k},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
        except httpx.ConnectError:
            logger.error("RagBase服务连接失败")
            return "错误：无法连接到RagBase知识库服务，请确认服务是否正在运行"
        except httpx.TimeoutException:
            logger.error("RagBase服务请求超时")
            return "错误：RagBase知识库检索超时"
        except httpx.HTTPStatusError as e:
            logger.error(f"RagBase服务返回错误: {e}")
            return f"错误：RagBase知识库检索失败，状态码 {e.response.status_code}"
        except Exception as e:
            logger.error(f"RagBase检索异常: {e}")
            return f"错误：知识库检索失败 - {e}"

        if result.get("code") != 0:
            return f"错误：{result.get('message', '未知错误')}"

        data = result.get("data", [])
        if not data:
            return "未检索到相关文档"

        import json
        results = []
        for item in data:
            results.append({
                "content": item.get("content", ""),
                "source": item.get("metadata", {}).get("filename", "未知来源"),
                "score": item.get("score", 0),
            })

        return json.dumps(results, ensure_ascii=False)
