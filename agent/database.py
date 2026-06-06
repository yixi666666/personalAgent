import sqlite3
from typing import Optional
from agent.config import get_config


_db_connection: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _db_connection
    if _db_connection is None:
        config = get_config()
        db_path = config.database_path
        _db_connection = sqlite3.connect(db_path, check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row
        _db_connection.execute("PRAGMA journal_mode=WAL")
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
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT NULL,
            status TEXT DEFAULT NULL,
            created_time INTEGER DEFAULT NULL,
            updated_time INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT DEFAULT NULL,
            parent_id TEXT DEFAULT NULL,
            role TEXT DEFAULT NULL,
            content TEXT DEFAULT NULL,
            created_time INTEGER DEFAULT NULL,
            updated_time INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id TEXT PRIMARY KEY,
            call_id TEXT DEFAULT NULL,
            message_id TEXT DEFAULT NULL,
            tool_name TEXT DEFAULT NULL,
            parameters TEXT DEFAULT NULL,
            result TEXT DEFAULT NULL,
            status TEXT DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            created_time INTEGER DEFAULT NULL,
            updated_time INTEGER DEFAULT NULL
        );
    """
    )
    db.commit()
