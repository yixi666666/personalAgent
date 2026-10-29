import logging

import httpx

from capabilityService.services.db_config import get_tool_config

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# 每条结果 raw_content 的最大保留字符数，防止撑爆上下文
RAW_CONTENT_MAX_CHARS = 3000


class WebSearchTool:
    """自研工具：调用 Tavily 搜索 API，返回网页链接与原文"""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "搜索互联网获取实时信息。返回结果列表，每条包含 title（网页标题）、"
            "url（链接）、content（与查询相关的原文段落）、score（相关度分数）和 "
            "raw_content（网页完整正文的截断版本）。适用于需要最新信息、"
            "知识库外部信息或事实核查的场景。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题",
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回的最大结果数，默认5，范围1-20",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "search_depth": {
                    "type": "string",
                    "description": "搜索深度：basic 快速，advanced 更全面但更慢",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
                "include_raw_content": {
                    "type": "boolean",
                    "description": "是否返回网页完整正文（截断版），默认true",
                    "default": True,
                },
                "topic": {
                    "type": "string",
                    "description": "搜索类别：general 通用，news 新闻（适合时效性查询）",
                    "enum": ["general", "news"],
                    "default": "general",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        search_depth = kwargs.get("search_depth", "basic")
        include_raw_content = kwargs.get("include_raw_content", True)
        topic = kwargs.get("topic", "general")

        api_key = get_tool_config("tool.tavily_api_key")
        if not api_key:
            return "错误：未配置 Tavily API Key，请在数据库 system_configs 表设置 tool.tavily_api_key（Fernet 密文存储）"

        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
            "topic": topic,
        }

        try:
            response = self._post(TAVILY_SEARCH_URL, payload, api_key, timeout=30.0)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("Tavily搜索请求超时")
            return "错误：网页搜索请求超时，可检查网络或配置 TAVILY_PROXY 代理后重试"
        except httpx.ConnectError:
            logger.error("Tavily API 连接失败")
            return "错误：无法连接 Tavily 搜索服务，可检查网络或配置 TAVILY_PROXY 代理后重试"
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error(f"Tavily API 返回错误: {status} {e}")
            if status == 401:
                return "错误：Tavily API Key 无效（401），请检查数据库 system_configs 表中的 tool.tavily_api_key"
            if status == 432:
                return "错误：Tavily 免费额度已用尽（432），请稍后再试或升级套餐"
            return f"错误：网页搜索失败，状态码 {status}"
        except Exception as e:
            logger.error(f"Tavily搜索异常: {e}")
            return f"错误：网页搜索失败 - {e}"

        result = response.json()

        results = result.get("results", [])
        if not results:
            return "未搜索到相关结果，可尝试更换关键词"

        output = []
        for item in results:
            entry = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0),
            }
            raw = item.get("raw_content")
            if raw:
                entry["raw_content"] = raw[:RAW_CONTENT_MAX_CHARS]
            output.append(entry)

        return output

    @staticmethod
    def _post(url: str, payload: dict, api_key: str, timeout: float) -> httpx.Response:
        """发送 POST 请求，支持通过 tool.tavily_proxy 配置代理"""
        proxy = get_tool_config("tool.tavily_proxy")
        client_kwargs = {"timeout": timeout}
        if proxy:
            client_kwargs["proxy"] = proxy
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(**client_kwargs) as client:
            return client.post(url, json=payload, headers=headers)
