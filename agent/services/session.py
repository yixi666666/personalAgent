import uuid
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from agent.database import get_db
from agent.models.session import (
    SessionListItem,
    SessionDetailResponse,
    MessageItem,
    ContentItem,
    ToolCallDetail,
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
    """将 UTC 时间戳转为 UTC+8 可读字符串，用于前端展示

    时间精确到分钟（不显示秒），仅用于会话级别时间
    """
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts, tz=UTC8)
    return dt.strftime('%Y-%m-%d %H:%M')


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
            "created_time": _format_display_time(now),
            "updated_time": _format_display_time(now),
        }

    def add_message(
        self, session_id: str, role: str, content: str = "", parent_id: Optional[str] = None,
        reasoning_content: str = "",
        reasoning_metadata: Optional[dict] = None,
    ) -> MessageItem:
        """添加消息，内容存入 message_contents 表

        适用于：用户消息、纯文本助手回复、系统消息
        reasoning_content: DeepSeek 深度思考内容，存为 type='reasoning'
        reasoning_metadata: reasoning 内容块的展示属性，如 {"tokens": 256, "finish_reason": "stop"}
        """
        msg_id = str(uuid.uuid4())
        now = _utc_now()
        db = get_db()
        db.execute(
            "INSERT INTO messages (id, session_id, parent_id, role, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, parent_id, role, now, now),
        )
        contents = []
        sort_order = 0
        if reasoning_content:
            mc_id = str(uuid.uuid4())
            metadata_json = json.dumps(reasoning_metadata, ensure_ascii=False) if reasoning_metadata else None
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, msg_id, "reasoning", reasoning_content, metadata_json, sort_order, now),
            )
            contents.append(ContentItem(type="reasoning", content=reasoning_content, metadata=reasoning_metadata, sort_order=sort_order))
            sort_order += 1
        if content:
            mc_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, msg_id, "text", content, None, sort_order, now),
            )
            contents.append(ContentItem(type="text", content=content, sort_order=sort_order))
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = ?",
            (now, session_id),
        )
        db.commit()
        return MessageItem(
            id=msg_id, parent_id=parent_id, role=role, contents=contents,
        )

    def add_assistant_message_with_tool_calls(
        self,
        session_id: str,
        content: str,
        tool_calls: list[dict],
        parent_id: Optional[str] = None,
        reasoning_content: str = "",
        reasoning_metadata: Optional[dict] = None,
    ) -> str:
        """添加带工具调用的助手消息

        按文档流程：
        1. 插入 messages 记录（role=assistant）
        2. 插入 message_contents 记录（reasoning + text + tool_call 类型）
        3. 插入 tool_calls 记录（status=pending）

        返回: 消息ID
        """
        msg_id = str(uuid.uuid4())
        now = _utc_now()
        db = get_db()
        # 1. 插入 messages 记录
        db.execute(
            "INSERT INTO messages (id, session_id, parent_id, role, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, parent_id, "assistant", now, now),
        )
        # 2. 插入 message_contents 记录
        sort_order = 0
        if reasoning_content:
            mc_id = str(uuid.uuid4())
            metadata_json = json.dumps(reasoning_metadata, ensure_ascii=False) if reasoning_metadata else None
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, msg_id, "reasoning", reasoning_content, metadata_json, sort_order, now),
            )
            sort_order += 1
        if content:
            mc_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, msg_id, "text", content, None, sort_order, now),
            )
            sort_order += 1
        for tc in tool_calls:
            call_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
            mc_id = str(uuid.uuid4())
            tool_name = tc.get("function", {}).get("name", "unknown")
            tool_metadata = {"tool_name": tool_name}
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, msg_id, "tool_call", call_id, json.dumps(tool_metadata, ensure_ascii=False), sort_order, now),
            )
            sort_order += 1
            # 3. 插入 tool_calls 记录（status=pending）
            arguments = tc.get("function", {}).get("arguments", "{}")
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            tc_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO tool_calls (id, call_id, message_id, tool_name, parameters, result, status, error_message, created_time, updated_time) VALUES (?, ?, ?, ?, ?, NULL, 'pending', NULL, ?, ?)",
                (tc_id, call_id, msg_id, tool_name, arguments, now, now),
            )
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = ?",
            (now, session_id),
        )
        db.commit()
        return msg_id

    def update_tool_call(
        self,
        call_id: str,
        message_id: str,
        result: str,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """更新工具调用记录的状态和结果

        使用 call_id + message_id 双条件定位，避免误更新历史记录
        """
        now = _utc_now()
        db = get_db()
        db.execute(
            "UPDATE tool_calls SET result = ?, status = ?, error_message = ?, updated_time = ? WHERE call_id = ? AND message_id = ?",
            (result, status, error_message, now, call_id, message_id),
        )
        # 更新会话的 updated_time
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = (SELECT session_id FROM messages WHERE id = ?)",
            (now, message_id),
        )
        db.commit()

    def update_message(self, message_id: str, content: str) -> bool:
        """更新消息内容，同时更新 updated_time

        更新 message_contents 表中 type='text' 的内容块
        """
        now = _utc_now()
        db = get_db()
        # 查找该消息的第一个 text 类型内容块
        mc_row = db.execute(
            "SELECT id FROM message_contents WHERE message_id = ? AND type = 'text' ORDER BY sort_order LIMIT 1",
            (message_id,),
        ).fetchone()
        if mc_row:
            db.execute(
                "UPDATE message_contents SET content = ? WHERE id = ?",
                (content, mc_row["id"]),
            )
        else:
            # 没有 text 内容块，创建一个
            mc_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO message_contents (id, message_id, type, content, metadata, sort_order, created_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mc_id, message_id, "text", content, None, 0, now),
            )
        # 更新消息的 updated_time
        db.execute(
            "UPDATE messages SET updated_time = ? WHERE id = ?",
            (now, message_id),
        )
        # 同步更新会话的 updated_time
        db.execute(
            "UPDATE sessions SET updated_time = ? WHERE id = (SELECT session_id FROM messages WHERE id = ?)",
            (now, message_id),
        )
        db.commit()
        return True

    def get_session(self, session_id: str) -> Optional[SessionDetailResponse]:
        """获取会话详情，返回格式符合文档规范（contents 数组）"""
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
        messages = []
        for row in msg_rows:
            # 从 message_contents 表读取内容块
            mc_rows = db.execute(
                "SELECT type, content, metadata, sort_order FROM message_contents WHERE message_id = ? ORDER BY sort_order",
                (row["id"],),
            ).fetchall()
            contents = []
            for mc in mc_rows:
                metadata = None
                if mc["metadata"]:
                    try:
                        metadata = json.loads(mc["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        metadata = None
                contents.append(ContentItem(
                    type=mc["type"],
                    content=mc["content"],
                    metadata=metadata,
                    sort_order=mc["sort_order"] or 0,
                ))
            msg_item = MessageItem(
                id=row["id"],
                parent_id=row["parent_id"],
                role=row["role"],
                contents=contents,
            )
            messages.append(msg_item)
        return SessionDetailResponse(
            id=session_row["id"],
            title=session_row["title"],
            status=session_row["status"],
            created_time=_format_display_time(session_row["created_time"]),
            updated_time=_format_display_time(session_row["updated_time"]),
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
                created_time=_format_display_time(row["created_time"]),
                updated_time=_format_display_time(row["updated_time"]),
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
        """获取会话的所有消息，用于构建LLM上下文

        按文档规范：
        - 从 messages + message_contents 读取对话历史
        - 对含 tool_call 内容块的 assistant 消息，从 tool_calls 表构造
          {"role":"tool","tool_call_id":"call_id","content":"result"} 消息，插入到该 assistant 消息之后
        - 不存储 role='tool' 的消息，tool 消息从 tool_calls 表动态生成
        """
        db = get_db()
        rows = db.execute(
            "SELECT id, role, parent_id FROM messages WHERE session_id = ? ORDER BY created_time",
            (session_id,),
        ).fetchall()

        messages = []
        for row in rows:
            msg = {"role": row["role"], "id": row["id"], "parent_id": row["parent_id"]}

            # 从 message_contents 表读取内容块
            mc_rows = db.execute(
                "SELECT type, content, sort_order FROM message_contents WHERE message_id = ? ORDER BY sort_order",
                (row["id"],),
            ).fetchall()

            if row["role"] == "assistant":
                # 检查是否有 tool_call 类型的内容块
                has_tool_calls = any(mc["type"] == "tool_call" for mc in mc_rows)

                if has_tool_calls:
                    # 构造 assistant 消息（含 tool_calls）
                    # 提取 reasoning/text 内容（reasoning 作为独立字段，不拼入 content）
                    text_parts = []
                    reasoning_parts = []
                    for mc in mc_rows:
                        if mc["type"] == "text":
                            text_parts.append(mc["content"] or "")
                        elif mc["type"] == "reasoning":
                            reasoning_parts.append(mc["content"] or "")
                    msg["content"] = "\n".join(text_parts) if text_parts else None
                    if reasoning_parts:
                        msg["reasoning_content"] = "\n".join(reasoning_parts)

                    # 从 tool_calls 表获取工具调用详情
                    tc_rows = db.execute(
                        "SELECT call_id, tool_name, parameters FROM tool_calls WHERE message_id = ? ORDER BY created_time",
                        (row["id"],),
                    ).fetchall()
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

                    messages.append(msg)

                    # 从 tool_calls 表构造 tool 消息，插入到 assistant 消息之后
                    tc_result_rows = db.execute(
                        "SELECT call_id, result FROM tool_calls WHERE message_id = ? ORDER BY created_time",
                        (row["id"],),
                    ).fetchall()
                    for tc in tc_result_rows:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["call_id"],
                            "content": tc["result"] or "",
                        })
                else:
                    # 普通助手消息（纯文本，reasoning 作为独立字段）
                    text_parts = []
                    reasoning_parts = []
                    for mc in mc_rows:
                        if mc["type"] == "text":
                            text_parts.append(mc["content"] or "")
                        elif mc["type"] == "reasoning":
                            reasoning_parts.append(mc["content"] or "")
                    msg["content"] = "\n".join(text_parts) if text_parts else ""
                    if reasoning_parts:
                        msg["reasoning_content"] = "\n".join(reasoning_parts)
                    messages.append(msg)
            else:
                # user / system 消息
                text_parts = []
                for mc in mc_rows:
                    if mc["type"] == "text":
                        text_parts.append(mc["content"] or "")
                msg["content"] = "\n".join(text_parts) if text_parts else ""
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

    def get_tool_calls_by_message(self, message_id: str) -> list[ToolCallDetail]:
        """获取指定消息下所有工具调用详情（懒加载接口使用）

        call_id 仅在同一条助手消息内唯一，需配合 message_id 定位
        """
        db = get_db()
        rows = db.execute(
            "SELECT call_id, message_id, tool_name, parameters, status, result FROM tool_calls WHERE message_id = ? ORDER BY created_time",
            (message_id,),
        ).fetchall()
        return [
            ToolCallDetail(
                call_id=row["call_id"],
                message_id=row["message_id"],
                tool_name=row["tool_name"],
                parameters=row["parameters"],
                status=row["status"],
                result=row["result"],
            )
            for row in rows
        ]


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
