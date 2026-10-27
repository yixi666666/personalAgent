from pydantic import BaseModel, Field
from typing import Optional


class AnnouncementItem(BaseModel):
    """公告列表项（用户端视角，仅返回已发布且到展示时间的公告）"""
    id: str
    title: str
    content: str
    is_pinned: bool = Field(default=False, description="是否置顶")
    publish_time: Optional[int] = Field(default=None, description="公告开始展示时间戳；NULL 表示立即可展示")
    popup_start_time: Optional[int] = Field(default=None, description="弹窗开始时间戳；NULL 表示不设置")
    popup_end_time: Optional[int] = Field(default=None, description="弹窗结束时间戳；NULL 表示不设置")
    is_read: bool = Field(default=False, description="当前用户是否已读")
    created_time: Optional[int] = None


class AnnouncementListResponse(BaseModel):
    """公告列表响应：置顶优先、发布时间倒序，附带未读数"""
    announcements: list[AnnouncementItem] = []
    unread_count: int = 0


class UnreadCountResponse(BaseModel):
    """未读公告数（导航铃铛红点）"""
    unread_count: int = 0
