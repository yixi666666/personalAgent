from pydantic import BaseModel
from typing import Optional, Any


class ContentItem(BaseModel):
    """消息内容块"""
    type: str  # 'text', 'reasoning', 'tool_call', 'image', 'file'
    content: Optional[str] = None
    metadata: Optional[Any] = None  # JSON 扩展属性，dict 或 None
    sort_order: int = 0


class SessionListItem(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    message_count: int = 0


class ToolCallDetail(BaseModel):
    """工具调用详情（懒加载接口返回）"""
    call_id: Optional[str] = None
    message_id: Optional[str] = None
    tool_name: Optional[str] = None
    parameters: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    parent_id: Optional[str] = None
    role: Optional[str] = None
    contents: list[ContentItem] = []


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
