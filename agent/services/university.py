"""高校信息查询服务

按高校全称从 universities 表读取该校的完整基础信息与实力数据（不含 facts / taxonomy）。
name + aliases 全局唯一，因此按 name 精确匹配即可定位唯一一行。
实力数据（排名 / 双一流建设学科 / 学科评估）通过 universities.code 与三表的 university_code 关联。
"""
import json
import logging
from typing import Optional

from agent.database import get_db

logger = logging.getLogger(__name__)

_SELECT_SQL = (
    "SELECT id, code, name, aliases, official_website, category, competent_department, "
    "province, city, edu_level, school_nature, tags, master_first, doctor_first, "
    "logo_url, raw_remark, created_time, updated_time "
    "FROM universities"
)

_LIST_SQL = _SELECT_SQL + " ORDER BY code"

_RANKING_SQL = (
    "SELECT source, year, rank_raw, rank_num, score FROM ranking_record "
    "WHERE university_code = ? ORDER BY source, year DESC"
)

_DOUBLE_FIRST_SQL = (
    "SELECT round, subjects, autonomous, note FROM double_first_subject "
    "WHERE university_code = ? ORDER BY round"
)

_DISCIPLINE_EVAL_SQL = (
    "SELECT round, disciplines FROM discipline_evaluation "
    "WHERE university_code = ? ORDER BY round"
)


def _parse_json_str_list(raw: Optional[str]) -> list[str]:
    """库中 JSON 数组字符串字段（aliases / tags）解析失败时返回空列表"""
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        logger.warning("JSON 数组字段解析失败: %s", raw)
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _parse_json_obj_list(raw: Optional[str]) -> list[dict]:
    """库中 JSON 数组字符串字段（subjects / disciplines）解析失败时返回空列表，元素仅保留 dict"""
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        logger.warning("JSON 数组字段解析失败: %s", raw)
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _parse_university_row(row) -> dict:
    """行 → dict，JSON 数组字段（aliases / tags）解析为列表"""
    info = dict(row)
    info["aliases"] = _parse_json_str_list(info.get("aliases"))
    info["tags"] = _parse_json_str_list(info.get("tags"))
    return info


def _attach_strength_data(info: dict) -> dict:
    """按 code 关联实力数据（排名 / 双一流建设学科 / 学科评估），无 code 时置空"""
    code = info.get("code")
    if not code:
        info["rankings"] = []
        info["double_first_subjects"] = []
        info["discipline_evaluations"] = []
        return info
    db = get_db()
    info["rankings"] = [
        dict(r) for r in db.execute(_RANKING_SQL, (code,)).fetchall()
    ]
    info["double_first_subjects"] = [
        {**dict(r), "subjects": _parse_json_obj_list(r["subjects"])}
        for r in db.execute(_DOUBLE_FIRST_SQL, (code,)).fetchall()
    ]
    info["discipline_evaluations"] = [
        {**dict(r), "disciplines": _parse_json_obj_list(r["disciplines"])}
        for r in db.execute(_DISCIPLINE_EVAL_SQL, (code,)).fetchall()
    ]
    return info


def get_university_by_name(name: str) -> Optional[dict]:
    """按高校全称查询，未命中返回 None"""
    row = get_db().execute(_SELECT_SQL + " WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    return _attach_strength_data(_parse_university_row(row))


def get_university_by_id(university_id: str) -> Optional[dict]:
    """按高校 id 查询（含实力数据），未命中返回 None"""
    row = get_db().execute(_SELECT_SQL + " WHERE id = ?", (university_id,)).fetchone()
    if not row:
        return None
    return _attach_strength_data(_parse_university_row(row))


def list_universities() -> list[dict]:
    """全部高校基础信息列表（不含实力数据），按标识码排序"""
    return [
        _parse_university_row(row)
        for row in get_db().execute(_LIST_SQL).fetchall()
    ]
