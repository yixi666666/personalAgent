from fastapi import APIRouter, Depends, HTTPException, Query

from agent.services.auth import get_current_user
from agent.models.session import (
    SessionListResponse,
    SessionDetailResponse,
    SessionUpdateRequest,
    RollbackResponse,
    ToolCallDetail,
)
from agent.services.session import get_session_manager

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=30, description="分页大小"),
    offset: int = Query(default=0, description="偏移量"),
    current_user: dict = Depends(get_current_user),
):
    session_manager = get_session_manager()
    result = session_manager.list_sessions(current_user["id"], limit, offset)
    return SessionListResponse(**result)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    session_manager = get_session_manager()
    result = session_manager.get_session(session_id, current_user["id"])
    if not result:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return result


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    session_manager = get_session_manager()
    success = session_manager.delete_session(session_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


@router.patch("/sessions/{session_id}", status_code=204)
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新会话（当前支持置顶/取消置顶）"""
    session_manager = get_session_manager()
    success = session_manager.set_pinned(session_id, current_user["id"], request.is_pinned)
    if not success:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


@router.post("/messages/{message_id}/rollback", response_model=RollbackResponse)
def rollback_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """回退到指定用户消息：该消息及其后所有消息软删，返回其文本供前端回填输入框"""
    session_manager = get_session_manager()
    result = session_manager.rollback_message(message_id, current_user["id"])
    if not result:
        raise HTTPException(
            status_code=404,
            detail="消息不存在或不可回退（仅支持回退到用户消息）",
        )
    return RollbackResponse(**result)


@router.get("/tool-calls", response_model=list[ToolCallDetail])
def get_tool_calls(
    message_id: str = Query(..., description="消息ID"),
    current_user: dict = Depends(get_current_user),
):
    """工具详情懒加载接口

    返回该消息下所有工具调用详情（call_id 仅在同一条助手消息内唯一，需配合 message_id 定位）
    """
    session_manager = get_session_manager()
    return session_manager.get_tool_calls_by_message(message_id, current_user["id"])
