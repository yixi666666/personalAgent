import sqlite3
import os
from typing import Optional
from app.config import get_config


_db_connection: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _db_connection
    if _db_connection is None:
        config = get_config()
        db_path = config.database_path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        _db_connection = sqlite3.connect(db_path, check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row
        _db_connection.execute("PRAGMA journal_mode=WAL")
        _db_connection.execute("PRAGMA foreign_keys=ON")
    return _db_connection


def close_db():
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            call_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            tool_args TEXT NOT NULL,
            result TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id);

        CREATE INDEX IF NOT EXISTS idx_tool_calls_conversation
            ON tool_calls(conversation_id);

        CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations(user_id);
    """
    )
    db.commit()
