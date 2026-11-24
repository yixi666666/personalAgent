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

_RANKING_SQL = (
    "SELECT source, year, rank_raw, rank_num, score FROM ranking_record "
    "WHERE university_code = ? ORDER BY source, year DESC"
)

_RANKING_MAX_SCORE_SQL = (
    "SELECT source, year, MAX(score) AS max_score FROM ranking_record "
    "GROUP BY source, year"
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
    # 同榜单同年的最高分，供前端展示 分数/最高分
    max_scores = {
        (r["source"], r["year"]): r["max_score"]
        for r in db.execute(_RANKING_MAX_SCORE_SQL).fetchall()
    }
    info["rankings"] = [
        {**dict(r), "max_score": max_scores.get((r["source"], r["year"]))}
        for r in db.execute(_RANKING_SQL, (code,)).fetchall()
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


def page_universities(
    page: int,
    page_size: int,
    keyword: str = "",
    province: str = "",
    tag: str = "",
    edu_level: str = "",
    category: str = "",
) -> dict:
    """条件分页查询高校基础信息（不含实力数据），按标识码排序

    keyword 模糊匹配 名称 / 标识码 / 别名；province / edu_level / category 精确匹配；
    tag 匹配 JSON 数组中的完整元素（带引号防止子串误命中）。
    """
    conditions: list[str] = []
    params: list = []
    if keyword:
        conditions.append("(name LIKE ? OR code LIKE ? OR aliases LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    if province:
        conditions.append("province = ?")
        params.append(province)
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if edu_level:
        conditions.append("edu_level = ?")
        params.append(edu_level)
    if category:
        conditions.append("category = ?")
        params.append(category)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM universities" + where, params
    ).fetchone()[0]
    rows = db.execute(
        _SELECT_SQL + where + " ORDER BY code LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return {
        "total": total,
        "items": [_parse_university_row(row) for row in rows],
    }


def university_summary() -> dict:
    """高校统计：总数 / 层次分布 / 标签分布 / 省份列表（供管理端筛选与卡片展示）"""
    db = get_db()
    total, bachelor = db.execute(
        "SELECT COUNT(*), SUM(CASE WHEN edu_level = '本科' THEN 1 ELSE 0 END) FROM universities"
    ).fetchone()
    tag_counts: dict[str, int] = {}
    for row in db.execute("SELECT tags FROM universities WHERE tags IS NOT NULL").fetchall():
        for tag in _parse_json_str_list(row["tags"]):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    provinces = [
        row["province"]
        for row in db.execute(
            "SELECT DISTINCT province FROM universities "
            "WHERE province IS NOT NULL AND province != '' ORDER BY province"
        ).fetchall()
    ]
    return {
        "total": total,
        "edu_level_counts": {"本科": bachelor or 0},
        "tag_counts": tag_counts,
        "provinces": provinces,
    }
