from pydantic import BaseModel
from typing import Optional


class SessionListItem(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    message_count: int = 0


class ToolCallInfo(BaseModel):
    """工具调用信息（用于历史消息展示）"""
    id: Optional[str] = None
    type: str = "function"
    function: dict = {}  # {"name": "...", "arguments": "..."}
    result: Optional[str] = None
    status: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    parent_id: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    tool_calls: Optional[list[ToolCallInfo]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]
    total: int
    limit: int
    offset: int


class SessionDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    messages: list[MessageItem] = []
