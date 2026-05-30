import uuid
import logging
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.conversation import (
    ConversationListItem,
    ConversationDetailResponse,
    MessageItem,
)

logger = logging.getLogger(__name__)


class ConversationManager:
    def create_conversation(self, user_id: str = "default_user") -> dict:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO conversations (conversation_id, user_id, created_at, updated_at, status) VALUES (?, ?, ?, ?, ?)",
            (conv_id, user_id, now, now, "active"),
        )
        db.commit()
        return {
            "conversation_id": conv_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "status": "active",
        }

    def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> MessageItem:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO messages (message_id, conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now),
        )
        db.execute(
            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
            (now, conversation_id),
        )
        db.commit()
        return MessageItem(
            message_id=msg_id, role=role, content=content, timestamp=now
        )

    def get_conversation(self, conversation_id: str) -> Optional[ConversationDetailResponse]:
        db = get_db()
        conv_row = db.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if not conv_row:
            return None
        msg_rows = db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        ).fetchall()
        messages = [
            MessageItem(
                message_id=row["message_id"],
                role=row["role"],
                content=row["content"],
                timestamp=row["timestamp"],
            )
            for row in msg_rows
        ]
        return ConversationDetailResponse(
            conversation_id=conv_row["conversation_id"],
            user_id=conv_row["user_id"],
            created_at=conv_row["created_at"],
            updated_at=conv_row["updated_at"],
            status=conv_row["status"],
            messages=messages,
        )

    def list_conversations(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> dict:
        db = get_db()
        total_row = db.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        total = total_row["cnt"]
        rows = db.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.conversation_id) as message_count "
            "FROM conversations c WHERE c.user_id = ? ORDER BY c.updated_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        conversations = [
            ConversationListItem(
                conversation_id=row["conversation_id"],
                user_id=row["user_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                status=row["status"],
                message_count=row["message_count"],
            )
            for row in rows
        ]
        return {
            "conversations": conversations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def delete_conversation(self, conversation_id: str) -> bool:
        db = get_db()
        conv_row = db.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if not conv_row:
            return False
        db.execute(
            "DELETE FROM tool_calls WHERE conversation_id = ?",
            (conversation_id,),
        )
        db.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        db.execute(
            "DELETE FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        )
        db.commit()
        return True

    def get_messages(self, conversation_id: str) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def conversation_exists(self, conversation_id: str) -> bool:
        db = get_db()
        row = db.execute(
            "SELECT 1 FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row is not None

    def save_tool_call(
        self,
        conversation_id: str,
        tool_name: str,
        tool_args: str,
        result: str,
    ):
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        db = get_db()
        db.execute(
            "INSERT INTO tool_calls (call_id, conversation_id, tool_name, tool_args, result, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (call_id, conversation_id, tool_name, tool_args, result, now),
        )
        db.commit()


_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
