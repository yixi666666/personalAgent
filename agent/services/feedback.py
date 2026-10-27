import json
import logging
import time
import uuid
from typing import Optional

from agent.database import get_db
from agent.models.feedback import (
    FeedbackReasonItem,
    FeedbackState,
)

logger = logging.getLogger(__name__)

VALID_FEEDBACK_TYPES = {"like", "dislike"}


def _utc_now() -> int:
    """返回当前 UTC 时间戳（秒）"""
    return int(time.time())


class FeedbackManager:
    def list_reasons(self, feedback_type: Optional[str] = None) -> list[FeedbackReasonItem]:
        """查询启用中的反馈原因字典，按 sort_order 排序

        feedback_type: 'like' | 'dislike'，返回该类型及 'all' 适用的原因；None 返回全部
        """
        db = get_db()
        if feedback_type in VALID_FEEDBACK_TYPES:
            rows = db.execute(
                "SELECT code, label, description FROM feedback_reasons "
                "WHERE status = 'active' AND feedback_type IN (?, 'all') ORDER BY sort_order",
                (feedback_type,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT code, label, description FROM feedback_reasons "
                "WHERE status = 'active' ORDER BY sort_order",
            ).fetchall()
        return [
            FeedbackReasonItem(code=row["code"], label=row["label"], description=row["description"])
            for row in rows
        ]

    def _validate_reason_codes(
        self, db, message_feedback_type: str, reason_codes: list[str],
    ) -> list[str]:
        """校验原因编码：必须为启用中且适用于该反馈类型的字典项，返回去重后的合法编码"""
        if not reason_codes:
            return []
        rows = db.execute(
            "SELECT code FROM feedback_reasons "
            "WHERE status = 'active' AND feedback_type IN (?, 'all')",
            (message_feedback_type,),
        ).fetchall()
        valid = {row["code"] for row in rows}
        invalid = [code for code in reason_codes if code not in valid]
        if invalid:
            raise ValueError(f"无效的反馈原因编码: {', '.join(invalid)}")
        # 去重且保序
        seen = set()
        return [code for code in reason_codes if not (code in seen or seen.add(code))]

    def _message_owner_role(self, db, message_id: str, user_id: str) -> Optional[str]:
        """校验消息存在、属于当前用户且为 active，返回其角色"""
        row = db.execute(
            "SELECT m.role FROM messages m JOIN sessions s ON s.id = m.session_id "
            "WHERE m.id = ? AND s.user_id = ? AND m.status = 'active'",
            (message_id, user_id),
        ).fetchone()
        return row["role"] if row else None

    def submit_feedback(
        self,
        user_id: str,
        message_id: str,
        feedback_type: str,
        reason_codes: Optional[list[str]] = None,
        comment: str = "",
    ) -> Optional[FeedbackState]:
        """提交反馈：单行 upsert —— 同一用户同一消息仅保留一条记录

        - 已有记录（无论撤销与否）则更新该行并置为 active，否则插入新行
        - 消息不存在、不属于当前用户或角色不是 assistant 时返回 None
        - 原因编码不合法抛 ValueError（路由层转 400）
        """
        if feedback_type not in VALID_FEEDBACK_TYPES:
            raise ValueError(f"无效的反馈类型: {feedback_type}")
        db = get_db()
        role = self._message_owner_role(db, message_id, user_id)
        if role is None or role != "assistant":
            return None
        valid_codes = self._validate_reason_codes(db, feedback_type, reason_codes or [])

        now = _utc_now()
        reason_json = json.dumps(valid_codes, ensure_ascii=False) if valid_codes else None
        existing = db.execute(
            "SELECT id FROM message_feedbacks WHERE message_id = ? AND user_id = ?",
            (message_id, user_id),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE message_feedbacks SET feedback_type = ?, reason_codes = ?, comment = ?, "
                "status = 'active', updated_time = ? WHERE id = ?",
                (feedback_type, reason_json, comment or None, now, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO message_feedbacks "
                "(id, message_id, user_id, feedback_type, reason_codes, comment, status, created_time, updated_time) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (
                str(uuid.uuid4()), message_id, user_id, feedback_type,
                reason_json,
                comment or None, now, now,
            ),
        )
        db.commit()
        return FeedbackState(
            message_id=message_id,
            feedback_type=feedback_type,
            reason_codes=valid_codes,
            comment=comment or "",
        )

    def revoke_feedback(self, user_id: str, message_id: str) -> bool:
        """撤销该用户对该消息的 active 反馈，返回是否撤销成功"""
        db = get_db()
        now = _utc_now()
        cursor = db.execute(
            "UPDATE message_feedbacks SET status = 'revoked', updated_time = ? "
            "WHERE message_id = ? AND user_id = ? AND status = 'active'",
            (now, message_id, user_id),
        )
        db.commit()
        return cursor.rowcount > 0

    def get_active_feedbacks(self, user_id: str, message_ids: list[str]) -> dict[str, FeedbackState]:
        """批量查询当前生效的反馈，返回 {message_id: FeedbackState}，用于会话详情回显"""
        if not message_ids:
            return {}
        db = get_db()
        placeholders = ",".join("?" for _ in message_ids)
        rows = db.execute(
            f"SELECT message_id, feedback_type, reason_codes, comment FROM message_feedbacks "
            f"WHERE user_id = ? AND status = 'active' AND message_id IN ({placeholders})",
            (user_id, *message_ids),
        ).fetchall()
        result = {}
        for row in rows:
            try:
                codes = json.loads(row["reason_codes"]) if row["reason_codes"] else []
            except (json.JSONDecodeError, TypeError):
                codes = []
            result[row["message_id"]] = FeedbackState(
                message_id=row["message_id"],
                feedback_type=row["feedback_type"],
                reason_codes=codes,
                comment=row["comment"] or "",
            )
        return result


_feedback_manager: Optional[FeedbackManager] = None


def get_feedback_manager() -> FeedbackManager:
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager()
    return _feedback_manager
