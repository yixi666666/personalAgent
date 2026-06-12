from fastapi import APIRouter, HTTPException, Query
from agent.models.session import (
    SessionListResponse,
    SessionDetailResponse,
    ToolCallDetail,
)
from agent.services.session import get_session_manager

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, description="分页大小"),
    offset: int = Query(default=0, description="偏移量"),
):
    session_manager = get_session_manager()
    result = session_manager.list_sessions(limit, offset)
    return SessionListResponse(**result)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: str):
    session_manager = get_session_manager()
    result = session_manager.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return result


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    session_manager = get_session_manager()
    success = session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


@router.get("/tool-calls", response_model=list[ToolCallDetail])
def get_tool_calls(message_id: str = Query(..., description="消息ID")):
    """工具详情懒加载接口

    返回该消息下所有工具调用详情（call_id 仅在同一条助手消息内唯一，需配合 message_id 定位）
    """
    session_manager = get_session_manager()
    return session_manager.get_tool_calls_by_message(message_id)
