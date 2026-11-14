from pydantic import BaseModel, Field
from typing import Optional

from agent.models.session import SessionDetailResponse


# ========== 系统配置 (system_configs) ==========

class SystemConfigItem(BaseModel):
    id: str
    key: str
    value: Optional[str] = None
    value_type: Optional[str] = None
    group_name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = False
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class SystemConfigCreate(BaseModel):
    key: str = Field(min_length=1, description="配置键，规范 {group}.{name}")
    value: Optional[str] = None
    value_type: str = Field(default="string", description="string|number|boolean|json|array")
    group_name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = False


class SystemConfigUpdate(BaseModel):
    value: Optional[str] = None
    value_type: Optional[str] = None
    group_name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


# ========== 模型配置 (models_configs) ==========

class ModelConfigItem(BaseModel):
    id: str
    name: Optional[str] = None
    model_type: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    has_api_key: bool = False
    base_url: Optional[str] = None
    api_prefix: Optional[str] = None
    is_enabled: bool = False
    priority: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    capabilities: dict = {}
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class ModelConfigCreate(BaseModel):
    model_id: str = Field(min_length=1)
    name: Optional[str] = None
    model_type: str = Field(default="chat", description="chat|embedding")
    provider: Optional[str] = None
    api_key: Optional[str] = Field(default=None, description="明文 api_key，后端加密入库")
    base_url: Optional[str] = None
    api_prefix: Optional[str] = None
    is_enabled: bool = True
    priority: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    capabilities: Optional[dict] = None


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    model_type: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    api_key: Optional[str] = Field(default=None, description="传入则重新加密覆盖；不传保持不变")
    base_url: Optional[str] = None
    api_prefix: Optional[str] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    capabilities: Optional[dict] = None


# ========== 用户管理 (users) ==========

class AdminUserItem(BaseModel):
    id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    last_login_time: Optional[int] = None
    last_login_ip: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = Field(default=None, description="user|admin|super_admin")
    status: Optional[str] = Field(default=None, description="active|disabled")


# ========== 公告管理 (announcements) ==========

class AdminAnnouncementItem(BaseModel):
    id: str
    title: str
    content: Optional[str] = None
    status: Optional[str] = None
    publish_time: Optional[int] = None
    is_pinned: bool = False
    popup_start_time: Optional[int] = None
    popup_end_time: Optional[int] = None
    created_by: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class AdminAnnouncementCreate(BaseModel):
    title: str = Field(min_length=1)
    content: Optional[str] = None
    status: str = Field(default="draft", description="draft|published|offline")
    publish_time: Optional[int] = None
    is_pinned: bool = False
    popup_start_time: Optional[int] = None
    popup_end_time: Optional[int] = None


class AdminAnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    publish_time: Optional[int] = None
    is_pinned: Optional[bool] = None
    popup_start_time: Optional[int] = None
    popup_end_time: Optional[int] = None


# ========== 反馈管理 (message_feedbacks / feedback_reasons) ==========

class AdminFeedbackItem(BaseModel):
    id: str
    message_id: str
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    feedback_type: Optional[str] = None
    reason_codes: list[str] = []
    comment: Optional[str] = None
    message_preview: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class AdminFeedbackReasonStat(BaseModel):
    code: str
    label: Optional[str] = None
    feedback_type: Optional[str] = None
    count: int


class AdminFeedbackStats(BaseModel):
    total_count: int = 0
    like_count: int = 0
    dislike_count: int = 0
    user_count: int = 0
    reason_stats: list[AdminFeedbackReasonStat] = []


class AdminFeedbackReasonItem(BaseModel):
    id: str
    code: str
    feedback_type: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    used_count: int = 0
    created_time: Optional[int] = None
    updated_time: Optional[int] = None


class AdminFeedbackReasonCreate(BaseModel):
    code: str = Field(min_length=1, description="稳定标识，全局唯一")
    feedback_type: str = Field(description="like | dislike | all")
    label: str = Field(min_length=1)
    description: Optional[str] = None
    status: str = Field(default="active", description="active | disabled")
    sort_order: int = Field(default=0)


class AdminFeedbackReasonUpdate(BaseModel):
    feedback_type: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None


class AdminFeedbackContext(BaseModel):
    """反馈上下文：与用户侧会话详情接口完全一致的数据 + 被评价消息定位"""
    feedback_message_id: str
    session: SessionDetailResponse
