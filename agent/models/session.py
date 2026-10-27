from pydantic import BaseModel, Field
from typing import Optional, Any

from agent.models.feedback import FeedbackState


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
    is_pinned: bool = False
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    message_count: int = 0


class SessionUpdateRequest(BaseModel):
    """会话更新请求（置顶等）"""
    is_pinned: bool = Field(..., description="是否置顶：true 置顶，false 取消置顶")


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
    feedback: Optional[FeedbackState] = None  # 当前用户对助手消息的反馈（点赞/拉踩）


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]
    total: int
    limit: int
    offset: int


class SessionDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None
    is_pinned: bool = False
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    messages: list[MessageItem] = []


class RollbackResponse(BaseModel):
    """消息回退响应：content 为被回退用户消息的文本，供前端回填输入框"""
    session_id: str
    message_id: str
    content: str
