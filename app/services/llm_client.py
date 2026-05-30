import json
import requests
import logging
from typing import Optional, Generator
from app.config import get_config
from app.services.context import sanitize_messages

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        config = get_config()
        self.base_url = config.model_base_url
        self.model_name = config.model_name
        self.max_tokens = config.model_max_tokens
        self.temperature = config.model_temperature

    def _resolve_provider(self, model: Optional[str] = None) -> dict:
        config = get_config()
        target_model = model or self.model_name
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

    def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        messages = sanitize_messages(messages)
        provider = self._resolve_provider(model)
        url = self._build_chat_url(provider)
        payload = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", self.max_tokens),
            "temperature": temperature or provider.get("temperature", self.temperature),
        }
        headers = self._build_headers(provider)
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=180,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM调用失败 [{provider['name']}]: {e}")
            raise RuntimeError(f"LLM调用失败 [{provider['name']}]: {e}") from e

    def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Generator[str, None, None]:
        messages = sanitize_messages(messages)
        provider = self._resolve_provider(model)
        url = self._build_chat_url(provider)
        payload = {
            "model": model or provider["name"],
            "messages": messages,
            "max_tokens": max_tokens or provider.get("max_tokens", self.max_tokens),
            "temperature": temperature or provider.get("temperature", self.temperature),
            "stream": True,
        }
        headers = self._build_headers(provider)
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=180,
                stream=True,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        data = decoded[6:]
                        if data.strip() == "[DONE]":
                            break
                        yield data
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM流式调用失败 [{provider['name']}]: {e}")
            raise RuntimeError(f"LLM流式调用失败 [{provider['name']}]: {e}") from e

    def get_models(self) -> dict:
        url = f"{self.base_url}/v1/models"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取模型列表失败: {e}")
            raise RuntimeError(f"获取模型列表失败: {e}") from e

    def score_evaluation(
        self,
        model: str,
        prompt: str,
        response_text: str,
        criteria: list[str],
    ) -> dict:
        url = f"{self.base_url}/v1/score/evaluation"
        payload = {
            "model": model,
            "prompt": prompt,
            "response": response_text,
            "criteria": criteria,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"评分评估失败: {e}")
            raise RuntimeError(f"评分评估失败: {e}") from e

    def analyze_tool_need(self, messages: list[dict]) -> dict:
        tool_analysis_prompt = (
            "请判断以下用户输入是否需要调用工具来回答。"
            "如果需要调用工具，请返回JSON格式的工具调用信息；如果不需要，请返回不需要工具的标识。\n\n"
            "可用工具列表：\n"
            "1. DateInfo - 获取当前日期和时间信息，无参数\n\n"
            "请务必严格按照以下JSON格式回复，绝对不要包含其他内容：\n"
            '{"need_tool": false, "tool_name": null, "tool_args": {}}\n'
            '或\n'
            '{"need_tool": true, "tool_name": "DateInfo", "tool_args": {}}\n\n'
            "判断规则：\n"
            "- 需要当前日期、时间、星期、几号等 → DateInfo\n"
            "- 普通对话、知识问答等 → 不需要工具\n\n"
            "用户输入："
        )
        last_user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user_msg = m["content"]
                break
        analysis_messages = [{"role": "user", "content": tool_analysis_prompt + last_user_msg}]
        try:
            result = self.chat(analysis_messages, temperature=0.1)
            content = result["choices"][0]["message"]["content"]
            import json

            content = content.strip()
            if content == "不需要工具":
                return {"need_tool": False, "tool_name": None, "tool_args": {}}
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
            content = content.strip()
            idx = content.find("{")
            if idx >= 0:
                content = content[idx:]
            decoder = json.JSONDecoder()
            analysis, _ = decoder.raw_decode(content)
            return analysis
        except Exception as e:
            logger.warning(f"工具调用分析失败，默认不需要工具: {e}")
            return {"need_tool": False, "tool_name": None, "tool_args": {}}


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
