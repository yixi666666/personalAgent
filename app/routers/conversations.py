from fastapi import APIRouter, HTTPException, Query
from app.models.conversation import (
    ConversationListResponse,
    ConversationDetailResponse,
    DeleteConversationResponse,
)
from app.services.conversation import get_conversation_manager

router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    user_id: str = Query(..., description="用户标识"),
    limit: int = Query(default=10, description="分页大小"),
    offset: int = Query(default=0, description="偏移量"),
):
    conv_manager = get_conversation_manager()
    result = conv_manager.list_conversations(user_id, limit, offset)
    return ConversationListResponse(**result)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: str):
    conv_manager = get_conversation_manager()
    result = conv_manager.get_conversation(conversation_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    return result


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str):
    conv_manager = get_conversation_manager()
    success = conv_manager.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
