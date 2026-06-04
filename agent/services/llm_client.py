import json
import logging
from typing import Optional, AsyncGenerator
import httpx
from agent.config import get_config
from agent.services.context import sanitize_messages

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        config = get_config()
        self.default_model = config.default_model
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=180.0)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def _resolve_provider(self, model: Optional[str] = None) -> dict:
        config = get_config()
        target_model = model or self.default_model
        return config.resolve_model_provider(target_model)

    def _build_headers(self, provider: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        api_key = provider.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_chat_url(self, provider: dict) -> str:
        base_url = provider["base_url"].rstrip("/")
        api_prefix = provider.get("api_prefix", "/v1").rstrip("/")
        return f"{base_url}{api_prefix}/chat/completions"

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict:
        messages = sanitize_messages(messages)
        provider = self._resolve_provider(model)
        url = self._build_chat_url(provider)
        payload: dict = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", 2048),
            "temperature": temperature if temperature is not None else provider.get("temperature", 0.7),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        # 星火模型关闭联网搜索
        if provider.get("provider") == "spark":
            payload["search_disable"] = True
        headers = self._build_headers(provider)
        try:
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM调用失败 [{provider['name']}]: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"LLM调用失败 [{provider['name']}]: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM调用失败 [{provider['name']}]: {e}")
            if provider.get("provider") == "local":
                raise RuntimeError(f"本地模型 [{provider['name']}] 不可用，请确认模型服务是否已启动（{provider.get('base_url', '')}）") from e
            raise RuntimeError(f"LLM调用失败 [{provider['name']}]: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        messages = sanitize_messages(messages)
        provider = self._resolve_provider(model)
        url = self._build_chat_url(provider)
        payload: dict = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", 2048),
            "temperature": temperature if temperature is not None else provider.get("temperature", 0.7),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        # 星火模型关闭联网搜索
        if provider.get("provider") == "spark":
            payload["search_disable"] = True
        headers = self._build_headers(provider)
        try:
            client = await self._get_http_client()
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                                break
                            yield data
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM流式调用失败 [{provider['name']}]: {e.response.status_code}")
            raise RuntimeError(f"LLM流式调用失败 [{provider['name']}]: {e.response.status_code}") from e
        except (httpx.RequestError, httpx.StreamError) as e:
            logger.error(f"LLM流式调用失败 [{provider['name']}]: {e}")
            if provider.get("provider") == "local":
                raise RuntimeError(f"本地模型 [{provider['name']}] 不可用，请确认模型服务是否已启动（{provider.get('base_url', '')}）") from e
            raise RuntimeError(f"LLM流式调用失败 [{provider['name']}]: {e}") from e


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
