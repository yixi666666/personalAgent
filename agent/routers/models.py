import logging
from fastapi import APIRouter
from agent.models.chat import ModelListResponse, ModelInfo, ModelCapabilities
from agent.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelListResponse)
def list_models():
    config = get_config()
    models = []
    for provider in config.get_all_model_providers():
        models.append(
            ModelInfo(
                id=provider["name"],
                name=provider["display_name"],
                description=f"{'本地部署' if provider['provider'] == 'local' else provider['display_name']}的大语言模型",
                provider=provider["provider"],
                status="available",
                capabilities=ModelCapabilities(
                    deep_thinking=provider.get("deep_thinking", False),
                    web_search=provider.get("web_search", False),
                    structured_output=provider.get("structured_output", False),
                    multimodal=provider.get("multimodal", False),
                    streaming=provider.get("streaming", True),
                    stop_anytime=provider.get("stop_anytime", True),
                    tool_calling=provider.get("supports_tools", True),
                    context_window=provider.get("context_window", 4096),
                ),
            )
        )
    model_ids = {model.id for model in models}
    default_model = config.default_model
    if default_model not in model_ids:
        if default_model:
            logger.error("默认模型不存在于模型列表中: %s", default_model)
        default_model = None
    return ModelListResponse(default_model=default_model, models=models)
