import os
import sqlite3
import logging
from typing import Optional
from agent.config import get_config

logger = logging.getLogger(__name__)

_db_connection: Optional[sqlite3.Connection] = None


def _backfill_messages_defaults(conn: sqlite3.Connection):
    """存量库结构补齐与数据回填（幂等，可重复执行）：
    1. 旧库缺列时在线补列（CREATE TABLE IF NOT EXISTS 不会更新已有表）
    2. status 统一回填 'active'（历史消息未写入 status）
    3. sequence 按会话内 created_time 顺序补齐（历史消息未写入 sequence）
    """
    msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    if "status" not in msg_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN status TEXT DEFAULT NULL")
    if "sequence" not in msg_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN sequence INTEGER DEFAULT NULL")
    sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "is_pinned" not in sess_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN is_pinned INTEGER DEFAULT NULL")
    conn.execute("UPDATE messages SET status = 'active' WHERE status IS NULL")
    conn.execute(
        "UPDATE messages SET sequence = ("
        "  SELECT COUNT(*) FROM messages m2"
        "  WHERE m2.session_id = messages.session_id"
        "    AND (m2.created_time < messages.created_time"
        "         OR (m2.created_time = messages.created_time AND m2.id <= messages.id))"
        ") WHERE sequence IS NULL"
    )
    conn.commit()


def get_db() -> sqlite3.Connection:
    global _db_connection
    if _db_connection is None:
        config = get_config()
        db_path = config.database_path
        if not os.path.isfile(db_path):
            raise FileNotFoundError("请运行init.sql初始化数据库")
        _db_connection = sqlite3.connect(db_path, check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row
        _db_connection.execute("PRAGMA journal_mode=WAL")
        _backfill_messages_defaults(_db_connection)
        # 加载 sqlite-vec 扩展，使向量表查询全局可用
        try:
            import sqlite_vec
            _db_connection.enable_load_extension(True)
            sqlite_vec.load(_db_connection)
            _db_connection.enable_load_extension(False)
            logger.info("sqlite-vec 扩展加载成功")
        except Exception as e:
            logger.warning(f"sqlite-vec 扩展加载失败（向量表不可用）: {e}")
    return _db_connection


def close_db():
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
