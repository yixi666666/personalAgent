import logging

import httpx

from capabilityService.services.db_config import get_tool_config

logger = logging.getLogger(__name__)

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"

# 正文最大保留字符数，防止撑爆上下文
RAW_CONTENT_MAX_CHARS = 8000


class WebFetchTool:
    """自研工具：调用 Tavily Extract API，抓取指定网页的完整正文"""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "抓取指定URL网页的完整正文内容（已清洗为纯文本，去除导航、广告等干扰元素）。"
            "适用于配合 web_search 使用：先搜索获得链接，再抓取感兴趣的网页阅读全文。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页URL",
                },
                "extract_depth": {
                    "type": "string",
                    "description": "提取深度：basic 快速，advanced 更强但更慢（适合反爬或JS渲染页面）",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "正文最大返回字符数，默认8000",
                    "default": 8000,
                },
            },
            "required": ["url"],
        }

    def execute(self, **kwargs) -> str:
        url = kwargs.get("url", "")
        extract_depth = kwargs.get("extract_depth", "basic")
        max_chars = kwargs.get("max_chars", RAW_CONTENT_MAX_CHARS)

        if not url.strip():
            return "错误：url 参数不能为空"

        api_key = get_tool_config("tool.tavily_api_key")
        if not api_key:
            return "错误：未配置 Tavily API Key，请在数据库 system_configs 表设置 tool.tavily_api_key（Fernet 密文存储）"

        payload = {
            "urls": [url],
            "extract_depth": extract_depth,
        }

        try:
            response = self._post(TAVILY_EXTRACT_URL, payload, api_key, timeout=60.0)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error(f"网页抓取请求超时: {url}")
            return "错误：网页抓取请求超时，可稍后重试或使用 extract_depth=advanced"
        except httpx.ConnectError:
            logger.error("Tavily API 连接失败")
            return "错误：无法连接 Tavily 服务，可检查网络或配置 TAVILY_PROXY 代理后重试"
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error(f"Tavily API 返回错误: {status} {e}")
            if status == 401:
                return "错误：Tavily API Key 无效（401），请检查数据库 system_configs 表中的 tool.tavily_api_key"
            if status == 432:
                return "错误：Tavily 免费额度已用尽（432），请稍后再试或升级套餐"
            return f"错误：网页抓取失败，状态码 {status}"
        except Exception as e:
            logger.error(f"网页抓取异常: {e}")
            return f"错误：网页抓取失败 - {e}"

        result = response.json()

        # Tavily 把失败的URL放在 failed_results 里
        failed = result.get("failed_results", [])
        if failed:
            fail_reason = failed[0].get("error", "未知原因")
            logger.warning(f"网页抓取失败: {url} - {fail_reason}")
            return (
                f"错误：无法提取该网页正文 - {fail_reason}。"
                f"可尝试使用 extract_depth=advanced 重新抓取"
            )

        results = result.get("results", [])
        if not results:
            return "错误：未获取到网页内容"

        raw_content = results[0].get("raw_content", "")
        if not raw_content:
            return (
                "错误：该网页没有可提取的正文内容。"
                "可尝试使用 extract_depth=advanced 重新抓取"
            )

        truncated = len(raw_content) > max_chars
        content = raw_content[:max_chars]
        if truncated:
            content += f"\n\n[注：正文过长已截断，原文共 {len(raw_content)} 字符]"

        return content

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
