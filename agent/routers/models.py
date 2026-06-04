import logging
from fastapi import APIRouter
from agent.models.chat import ModelListResponse, ModelInfo
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
            )
        )
    return ModelListResponse(models=models)
