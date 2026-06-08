import os

from openai import OpenAI

from app.config import get_config

SYSTEM_TEMPLATE = (
    "你是一个知识问答助手。请根据以下检索到的知识片段回答用户的问题。"
    "如果知识片段中没有相关信息，请如实说明。"
    "请在回答末尾标注参考来源（文件名）。\n\n"
    "知识片段：\n{context}"
)


def _get_llm_config() -> tuple[dict, str]:
    config = get_config()
    llm_cfg = config["llm"]
    provider = llm_cfg["default"]
    return llm_cfg[provider], provider


def _build_client(cfg: dict, provider: str) -> OpenAI:
    base_url = cfg["base_url"]
    api_key = cfg.get("api_key", "")
    if not api_key:
        api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env, "not-needed")
    return OpenAI(base_url=base_url, api_key=api_key)


def chat(prompt: str, context: str, model: str | None = None) -> str:
    config = get_config()
    llm_cfg = config["llm"]

    # 如果指定了 model 参数，尝试匹配对应的 provider
    provider = model if model and model in llm_cfg else llm_cfg["default"]
    provider_cfg = llm_cfg[provider]

    client = _build_client(provider_cfg, provider)
    response = client.chat.completions.create(
        model=provider_cfg["model"],
        messages=[
            {"role": "system", "content": SYSTEM_TEMPLATE.format(context=context)},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content
