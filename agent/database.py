import os
import sqlite3
from typing import Optional
from agent.config import get_config


_db_connection: Optional[sqlite3.Connection] = None


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
    return _db_connection


def close_db():
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
