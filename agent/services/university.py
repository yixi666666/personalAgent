"""高校信息查询服务

按高校全称从 universities 表读取该校的完整基础信息（不含 facts / taxonomy）。
name + aliases 全局唯一，因此按 name 精确匹配即可定位唯一一行。
"""
import json
import logging
from typing import Optional

from agent.database import get_db

logger = logging.getLogger(__name__)

_SELECT_SQL = (
    "SELECT id, code, name, aliases, official_website, category, competent_department, "
    "province, city, edu_level, school_nature, raw_remark, created_time, updated_time "
    "FROM universities WHERE name = ?"
)


def _parse_aliases(raw: Optional[str]) -> list[str]:
    """库中 aliases 为 JSON 数组字符串，解析失败时返回空列表"""
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        logger.warning("别名解析失败: %s", raw)
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def get_university_by_name(name: str) -> Optional[dict]:
    """按高校全称查询，未命中返回 None"""
    db = get_db()
    row = db.execute(_SELECT_SQL, (name,)).fetchone()
    if not row:
        return None
    info = dict(row)
    info["aliases"] = _parse_aliases(info.get("aliases"))
    return info
