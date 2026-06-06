from fastapi import APIRouter, HTTPException, Query
from agent.models.session import (
    SessionListResponse,
    SessionDetailResponse,
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
