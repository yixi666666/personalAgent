from pydantic import BaseModel
from typing import Optional


class SessionListItem(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None
    message_count: int = 0


class MessageItem(BaseModel):
    id: str
    parent_id: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]
    total: int
    limit: int
    offset: int


class SessionDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None
    messages: list[MessageItem] = []
