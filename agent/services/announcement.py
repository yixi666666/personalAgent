import logging
import time
from typing import Optional, Tuple

from agent.database import get_db
from agent.models.announcement import AnnouncementItem

logger = logging.getLogger(__name__)


def _utc_now() -> int:
    """返回当前 UTC 时间戳（秒）"""
    return int(time.time())


class AnnouncementManager:
    """公告用户端逻辑

    可见公告定义：status='published' 且 publish_time 已到（NULL 表示立即可展示）。
    已读状态存于 announcement_reads，联合主键保证同一用户对同一公告仅一条记录。
    """

    @staticmethod
    def _visible_clause() -> str:
        return "a.status = 'published' AND (a.publish_time IS NULL OR a.publish_time <= ?)"

    def list_announcements(self, user_id: str) -> Tuple[list[AnnouncementItem], int]:
        """当前用户可见的公告列表，置顶优先、发布时间倒序；返回 (列表, 未读数)"""
        db = get_db()
        rows = db.execute(
            "SELECT a.id, a.title, a.content, a.is_pinned, a.publish_time, "
            "       a.popup_start_time, a.popup_end_time, a.created_time, "
            "       r.user_id IS NOT NULL AS is_read "
            "FROM announcements a "
            "LEFT JOIN announcement_reads r "
            "       ON r.announcement_id = a.id AND r.user_id = ? "
            f"WHERE {self._visible_clause()} "
            "ORDER BY a.is_pinned DESC, COALESCE(a.publish_time, a.created_time) DESC",
            (user_id, _utc_now()),
        ).fetchall()
        items = [
            AnnouncementItem(
                id=row["id"],
                title=row["title"],
                content=row["content"] or "",
                is_pinned=bool(row["is_pinned"]),
                publish_time=row["publish_time"],
                popup_start_time=row["popup_start_time"],
                popup_end_time=row["popup_end_time"],
                is_read=bool(row["is_read"]),
                created_time=row["created_time"],
            )
            for row in rows
        ]
        unread_count = sum(1 for item in items if not item.is_read)
        return items, unread_count

    def get_unread_count(self, user_id: str) -> int:
        """当前用户未读的可见公告数"""
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) AS cnt FROM announcements a "
            "LEFT JOIN announcement_reads r "
            "       ON r.announcement_id = a.id AND r.user_id = ? "
            f"WHERE {self._visible_clause()} AND r.user_id IS NULL",
            (user_id, _utc_now()),
        ).fetchone()
        return row["cnt"] if row else 0

    def mark_read(self, user_id: str, announcement_id: str) -> bool:
        """标记公告已读：公告必须当前可见，否则返回 False；重复标记幂等（保留首次已读时间）"""
        db = get_db()
        exists = db.execute(
            f"SELECT 1 FROM announcements a WHERE a.id = ? AND {self._visible_clause()}",
            (announcement_id, _utc_now()),
        ).fetchone()
        if not exists:
            return False
        db.execute(
            "INSERT OR IGNORE INTO announcement_reads (user_id, announcement_id, read_time) "
            "VALUES (?, ?, ?)",
            (user_id, announcement_id, _utc_now()),
        )
        db.commit()
        return True


_announcement_manager: Optional[AnnouncementManager] = None


def get_announcement_manager() -> AnnouncementManager:
    global _announcement_manager
    if _announcement_manager is None:
        _announcement_manager = AnnouncementManager()
    return _announcement_manager
