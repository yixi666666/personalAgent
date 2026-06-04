from pydantic import BaseModel
from typing import Optional


class ConversationBase(BaseModel):
    conversation_id: str
    user_id: str
    created_at: str
    updated_at: str
    status: str = "active"


class ConversationDetail(ConversationBase):
    messages: list["MessageItem"] = []


class ConversationListItem(BaseModel):
    conversation_id: str
    user_id: str
    created_at: str
    updated_at: str
    status: str
    message_count: int = 0


class MessageItem(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItem]
    total: int
    limit: int
    offset: int


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    user_id: str
    created_at: str
    updated_at: str
    status: str
    messages: list[MessageItem] = []


class DeleteConversationResponse(BaseModel):
    message: str = "会话已删除"
