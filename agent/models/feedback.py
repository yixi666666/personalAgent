from pydantic import BaseModel, Field
from typing import Optional


class FeedbackReasonItem(BaseModel):
    """反馈原因字典项"""
    code: str
    label: str
    description: Optional[str] = None


class FeedbackReasonsResponse(BaseModel):
    reasons: list[FeedbackReasonItem]


class FeedbackSubmitRequest(BaseModel):
    """提交/更新反馈：同一用户对同一消息仅保留一条 active 反馈，切换类型时旧记录置为 revoked"""
    message_id: str = Field(..., description="被评价的消息ID（助手消息）")
    feedback_type: str = Field(..., description="反馈类型：'like' | 'dislike'")
    reason_codes: list[str] = Field(default=[], description="反馈原因编码列表，如 ['incorrect','other']")
    comment: str = Field(default="", description="用户填写的补充说明")


class FeedbackState(BaseModel):
    """当前生效的反馈状态（会话详情回显 / 提交响应）"""
    message_id: str
    feedback_type: str
    reason_codes: list[str] = []
    comment: str = ""
