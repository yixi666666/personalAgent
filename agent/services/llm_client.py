import json
import logging
from typing import Optional, AsyncGenerator

from openai import AsyncOpenAI, APIStatusError, APIConnectionError

from agent.config import get_config
from agent.services.context import sanitize_messages

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        config = get_config()
        self.default_model = config.default_model
        self._clients: dict[str, AsyncOpenAI] = {}

    def _get_client(self, provider: dict) -> AsyncOpenAI:
        """根据 provider 配置获取或创建 AsyncOpenAI 客户端"""
        provider_key = provider.get("provider", "")
        if provider_key not in self._clients:
            base_url = provider["base_url"].rstrip("/")
            api_prefix = provider.get("api_prefix", "/v1").rstrip("/")
            full_base_url = f"{base_url}{api_prefix}"
            api_key = provider.get("api_key") or "not-needed"
            self._clients[provider_key] = AsyncOpenAI(
                base_url=full_base_url,
                api_key=api_key,
                timeout=180.0,
            )
        return self._clients[provider_key]

    async def close(self):
        for key, client in self._clients.items():
            await client.close()
        self._clients.clear()

    def _resolve_provider(self, model: Optional[str] = None) -> dict:
        config = get_config()
        target_model = model or self.default_model
        return config.resolve_model_provider(target_model)

    def _build_extra_body(self, provider: dict, stream: bool) -> dict:
        """构建 extra_body：星火模型关闭联网搜索，非本地模型流式时包含 stream_options"""
        extra: dict = {}
        if provider.get("provider") == "spark":
            extra["search_disable"] = True
        if stream and provider.get("provider") != "local":
            extra["stream_options"] = {"include_usage": True}
        return extra or None

    async def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list[dict]] = None,
        supports_tools: bool = True,
    ) -> dict:
        """非流式调用LLM（用于本地模型 stream=false + tools）"""
        messages = sanitize_messages(messages, supports_tools=supports_tools)
        provider = self._resolve_provider(model)
        client = self._get_client(provider)

        kwargs: dict = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", 2048),
            "temperature": temperature if temperature is not None else provider.get("temperature", 0.7),
            "stream": False,
        }
        # 本地模型（LLaMA-Factory）不会用 chat_template 渲染 tools 参数，
        # 工具格式指令已通过系统提示词注入，不需要传 tools/tool_choice 参数
        if tools and supports_tools and provider.get("provider") != "local":
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        extra_body = self._build_extra_body(provider, stream=False)
        if extra_body:
            kwargs["extra_body"] = extra_body

        logger.debug(f"[DEBUG] 非流式调用参数: model={kwargs.get('model')}, provider={provider.get('provider')}")

        try:
            response = await client.chat.completions.create(**kwargs)
            result = response.model_dump()
            logger.debug(f"[DEBUG] 非流式调用完整返回: {json.dumps(result, ensure_ascii=False)}")
            return result
        except APIStatusError as e:
            logger.error(f"LLM非流式调用失败 [{provider['name']}]: {e.status_code}")
            raise RuntimeError(f"LLM非流式调用失败 [{provider['name']}]: {e.status_code}") from e
        except APIConnectionError as e:
            logger.error(f"LLM非流式调用失败 [{provider['name']}]: {e}")
            if provider.get("provider") == "local":
                raise RuntimeError(f"本地模型 [{provider['name']}] 不可用，请确认模型服务是否已启动（{provider.get('base_url', '')}）") from e
            raise RuntimeError(f"LLM非流式调用失败 [{provider['name']}]: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list[dict]] = None,
        supports_tools: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """流式调用LLM，yield SDK 解析后的 chunk dict"""
        messages = sanitize_messages(messages, supports_tools=supports_tools)
        provider = self._resolve_provider(model)
        client = self._get_client(provider)

        kwargs: dict = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", 2048),
            "temperature": temperature if temperature is not None else provider.get("temperature", 0.7),
            "stream": True,
        }
        # 仅当模型支持function calling时才发送tools参数
        if tools and supports_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        extra_body = self._build_extra_body(provider, stream=True)
        if extra_body:
            kwargs["extra_body"] = extra_body

        logger.debug(f"[DEBUG] 流式调用参数: model={kwargs.get('model')}, provider={provider.get('provider')}")

        try:
            chunks_data = []
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                chunk_dict = chunk.model_dump()
                chunks_data.append(chunk_dict)
                yield chunk_dict
            logger.debug(f"[DEBUG] 流式调用完整返回: {json.dumps(chunks_data, ensure_ascii=False)}")
        except APIStatusError as e:
            logger.error(f"LLM流式调用失败 [{provider['name']}]: {e.status_code}")
            raise RuntimeError(f"LLM流式调用失败 [{provider['name']}]: {e.status_code}") from e
        except APIConnectionError as e:
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
