import logging
from fastapi import APIRouter, HTTPException
from app.models.chat import ScoreRequest, ScoreResponse
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/score/evaluation", response_model=ScoreResponse)
def score_evaluation(request: ScoreRequest):
    llm_client = get_llm_client()
    try:
        result = llm_client.score_evaluation(
            model=request.model,
            prompt=request.prompt,
            response_text=request.response,
            criteria=request.criteria,
        )
        return ScoreResponse(**result)
    except Exception as e:
        logger.error(f"评分评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评分评估失败: {e}")
