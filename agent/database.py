import os
import sqlite3
import logging
from typing import Optional
from agent.config import get_config

logger = logging.getLogger(__name__)

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
