from fastapi import APIRouter, Depends, HTTPException, status

from agent.models.announcement import AnnouncementListResponse, UnreadCountResponse
from agent.services.announcement import get_announcement_manager
from agent.services.auth import get_current_user

router = APIRouter()


@router.get("/announcements", response_model=AnnouncementListResponse)
def list_announcements(current_user: dict = Depends(get_current_user)):
    """当前用户可见的公告列表（置顶优先、发布时间倒序），含未读数"""
    items, unread_count = get_announcement_manager().list_announcements(current_user["id"])
    return AnnouncementListResponse(announcements=items, unread_count=unread_count)


@router.get("/announcements/unread-count", response_model=UnreadCountResponse)
def get_unread_count(current_user: dict = Depends(get_current_user)):
    """当前用户未读公告数，用于导航铃铛红点"""
    count = get_announcement_manager().get_unread_count(current_user["id"])
    return UnreadCountResponse(unread_count=count)


@router.post("/announcements/{announcement_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_announcement_read(announcement_id: str, current_user: dict = Depends(get_current_user)):
    """标记公告已读：重复标记幂等；公告不存在或不可见返回 404"""
    success = get_announcement_manager().mark_read(current_user["id"], announcement_id)
    if not success:
        raise HTTPException(status_code=404, detail="公告不存在或不可见")
