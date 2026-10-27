from fastapi import APIRouter, Depends, HTTPException, Query

from agent.models.feedback import (
    FeedbackReasonsResponse,
    FeedbackState,
    FeedbackSubmitRequest,
)
from agent.services.auth import get_current_user
from agent.services.feedback import get_feedback_manager

router = APIRouter()


@router.get("/feedbacks/reasons", response_model=FeedbackReasonsResponse)
def list_feedback_reasons(
    feedback_type: str = Query(default=None, description="按类型过滤：'like' | 'dislike'，不传返回全部"),
    current_user: dict = Depends(get_current_user),
):
    """反馈原因字典：返回启用中的原因项（含 'all' 类型），按 sort_order 排序"""
    reasons = get_feedback_manager().list_reasons(feedback_type)
    return FeedbackReasonsResponse(reasons=reasons)


@router.put("/feedbacks", response_model=FeedbackState)
def submit_feedback(
    request: FeedbackSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交/更新消息反馈（点赞或拉踩）：同消息同用户仅保留一条 active 记录"""
    try:
        state = get_feedback_manager().submit_feedback(
            user_id=current_user["id"],
            message_id=request.message_id,
            feedback_type=request.feedback_type,
            reason_codes=request.reason_codes,
            comment=request.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if state is None:
        raise HTTPException(status_code=404, detail="消息不存在或不可评价")
    return state


@router.delete("/feedbacks/{message_id}", status_code=204)
def revoke_feedback(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    """撤销当前用户对该消息的反馈"""
    success = get_feedback_manager().revoke_feedback(current_user["id"], message_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到生效的反馈记录")
