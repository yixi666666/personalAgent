import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from agent.database import get_db
from agent.models.session import (
    SessionListItem,
    SessionDetailResponse,
    MessageItem,
)

logger = logging.getLogger(__name__)

# UTC+8 时区
UTC8 = timezone(timedelta(hours=8))


def _utc_now() -> int:
    """返回当前 UTC 时间戳（秒）"""
    return int(time.time())


def _format_title(ts: int) -> str:
    """根据时间戳生成标题，格式：对话 MM-DD HH:MM:SS（UTC+8）"""
    dt = datetime.fromtimestamp(ts, tz=UTC8)
    return f"对话 {dt.strftime('%m-%d %H:%M:%S')}"


def _format_display_time(ts: Optional[int]) -> Optional[str]:
    """将 UTC 时间戳转为 UTC+8 可读字符串，用于前端展示"""
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts, tz=UTC8)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


class SessionManager:
    def create_session(self) -> dict:
        session_id = str(uuid.uuid4())
        now = _utc_now()
        title = _format_title(now)
        db = get_db()
        db.execute(
            "INSERT INTO sessions (id, title, status, created_time, updated_time) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, "active", now, now),
        )
        db.commit()
        return {
            "id": session_id,
            "title": title,
            "status": "active",
            "created_time": now,
            "updated_time": now,
        }

    def add_message(
        self, session_id: str, role: str, content: str, parent_id: Optional[str] = None
    ) -> MessageItem:
        msg_id = str(uuid.uuid4())
        now = _utc_now()
        db = get_db()
        db.execute(
            "INSERT INTO messages (id, session_id, parent_id, role, content, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, parent_id, role, content, now, now),
        )
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = ?",
            (now, session_id),
        )
        db.commit()
        return MessageItem(
            id=msg_id, parent_id=parent_id, role=role, content=content, created_time=now, updated_time=now
        )

    def update_message(self, message_id: str, content: str) -> bool:
        """更新消息内容，同时更新 updated_time"""
        now = _utc_now()
        db = get_db()
        cursor = db.execute(
            "UPDATE messages SET content = ?, updated_time = ? WHERE id = ?",
            (content, now, message_id),
        )
        if cursor.rowcount == 0:
            return False
        # 同步更新会话的 updated_time
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = (SELECT session_id FROM messages WHERE id = ?)",
            (now, message_id),
        )
        db.commit()
        return True

    def get_session(self, session_id: str) -> Optional[SessionDetailResponse]:
        db = get_db()
        session_row = db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not session_row:
            return None
        msg_rows = db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_time",
            (session_id,),
        ).fetchall()
        messages = [
            MessageItem(
                id=row["id"],
                parent_id=row["parent_id"],
                role=row["role"],
                content=row["content"],
                created_time=row["created_time"],
                updated_time=row["updated_time"],
            )
            for row in msg_rows
        ]
        return SessionDetailResponse(
            id=session_row["id"],
            title=session_row["title"],
            status=session_row["status"],
            created_time=session_row["created_time"],
            updated_time=session_row["updated_time"],
            messages=messages,
        )

    def list_sessions(
        self, limit: int = 20, offset: int = 0
    ) -> dict:
        db = get_db()
        total_row = db.execute(
            "SELECT COUNT(*) as cnt FROM sessions WHERE status != 'deleted'",
        ).fetchone()
        total = total_row["cnt"]
        rows = db.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) as message_count "
            "FROM sessions s WHERE s.status != 'deleted' ORDER BY s.updated_time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        sessions = [
            SessionListItem(
                id=row["id"],
                title=row["title"],
                status=row["status"],
                created_time=row["created_time"],
                updated_time=row["updated_time"],
                message_count=row["message_count"],
            )
            for row in rows
        ]
        return {
            "sessions": sessions,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def delete_session(self, session_id: str) -> bool:
        """软删除：将session状态标记为deleted"""
        db = get_db()
        session_row = db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not session_row:
            return False
        now = _utc_now()
        db.execute(
            "UPDATE sessions SET status = 'deleted', updated_time = ? WHERE id = ?",
            (now, session_id),
        )
        db.commit()
        return True

    def get_messages(self, session_id: str) -> list[dict]:
        """获取会话的所有消息，包含工具调用相关信息，用于构建完整上下文"""
        db = get_db()
        rows = db.execute(
            "SELECT id, role, content, parent_id FROM messages WHERE session_id = ? ORDER BY created_time",
            (session_id,),
        ).fetchall()

        messages = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"], "id": row["id"], "parent_id": row["parent_id"]}

            # 如果是assistant消息，检查是否有关联的tool_calls
            if row["role"] == "assistant":
                tc_rows = db.execute(
                    "SELECT call_id, tool_name, parameters FROM tool_calls WHERE message_id = ? ORDER BY created_time",
                    (row["id"],),
                ).fetchall()
                if tc_rows:
                    msg["tool_calls"] = [
                        {
                            "id": tc["call_id"],
                            "type": "function",
                            "function": {
                                "name": tc["tool_name"],
                                "arguments": tc["parameters"],
                            },
                        }
                        for tc in tc_rows
                    ]

            # 如果是tool消息，添加tool_call_id和name
            if row["role"] == "tool":
                # tool消息的parent_id指向assistant消息，从assistant消息的tool_calls中找到对应的tool_call
                if row["parent_id"]:
                    tc_row = db.execute(
                        "SELECT call_id, tool_name FROM tool_calls WHERE message_id = ? ORDER BY created_time",
                        (row["parent_id"],),
                    ).fetchall()
                    # 找到与当前tool消息对应的tool_call
                    # tool消息按顺序对应assistant消息的tool_calls
                    parent_tool_msgs = db.execute(
                        "SELECT id FROM messages WHERE parent_id = ? AND role = 'tool' ORDER BY created_time",
                        (row["parent_id"],),
                    ).fetchall()
                    for idx, tm in enumerate(parent_tool_msgs):
                        if tm["id"] == row["id"] and idx < len(tc_row):
                            msg["tool_call_id"] = tc_row[idx]["call_id"]
                            msg["name"] = tc_row[idx]["tool_name"]
                            break

            messages.append(msg)
        return messages

    def session_exists(self, session_id: str) -> bool:
        db = get_db()
        row = db.execute(
            "SELECT 1 FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return row is not None

    def get_last_message_id(self, session_id: str) -> Optional[str]:
        """获取会话中最后一条消息的 ID，用于 parent_id 关联"""
        db = get_db()
        row = db.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY created_time DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return row["id"] if row else None

    def create_tool_call(
        self,
        message_id: str,
        tool_name: str,
        parameters: str,
        call_id: Optional[str] = None,
    ) -> str:
        """创建工具调用记录（pending状态）

        Args:
            call_id: 模型返回的调用ID，以"call_"开头，用于关联工具结果
        """
        tc_id = str(uuid.uuid4())
        now = _utc_now()
        db = get_db()
        db.execute(
            "INSERT INTO tool_calls (id, call_id, message_id, tool_name, parameters, result, status, error_message, created_time, updated_time) VALUES (?, ?, ?, ?, ?, NULL, 'pending', NULL, ?, ?)",
            (tc_id, call_id, message_id, tool_name, parameters, now, now),
        )
        db.commit()
        return tc_id

    def update_tool_call(
        self,
        call_id: str,
        result: str,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """更新工具调用记录的状态和结果"""
        now = _utc_now()
        db = get_db()
        db.execute(
            "UPDATE tool_calls SET result = ?, status = ?, error_message = ?, updated_time = ? WHERE id = ?",
            (result, status, error_message, now, call_id),
        )
        # 更新会话的 updated_time
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = (SELECT session_id FROM messages WHERE id = (SELECT message_id FROM tool_calls WHERE id = ?))",
            (now, call_id),
        )
        db.commit()

    def save_tool_call(
        self,
        message_id: str,
        tool_name: str,
        parameters: str,
        result: str,
        status: str = "success",
        error_message: Optional[str] = None,
        call_id: Optional[str] = None,
    ):
        """创建工具调用记录（兼容直接创建success状态的快捷方法）

        Args:
            call_id: 模型返回的调用ID，以"call_"开头，用于关联工具结果
        """
        tc_id = str(uuid.uuid4())
        now = _utc_now()
        db = get_db()
        db.execute(
            "INSERT INTO tool_calls (id, call_id, message_id, tool_name, parameters, result, status, error_message, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tc_id, call_id, message_id, tool_name, parameters, result, status, error_message, now, now),
        )
        # 更新会话的 updated_time
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = (SELECT session_id FROM messages WHERE id = ?)",
            (now, message_id),
        )
        db.commit()
        return tc_id


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
