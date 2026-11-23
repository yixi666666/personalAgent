"""管理端路由：系统配置 / 模型配置 / 用户管理 / 公告管理 / 反馈管理。

- 全部接口要求 admin / super_admin 角色（router 级 require_admin 依赖）
- 时间字段：UTC 秒，应用层填充
- 模型 api_key 复用 model_service 的 Fernet 加密，明文仅在请求中出现，不回传
"""

import json
import logging
import sqlite3
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from agent.database import get_db
from agent.models.admin import (
    AdminAnnouncementCreate,
    AdminAnnouncementItem,
    AdminAnnouncementUpdate,
    AdminFeedbackContext,
    AdminFeedbackItem,
    AdminFeedbackReasonCreate,
    AdminFeedbackReasonItem,
    AdminFeedbackReasonStat,
    AdminFeedbackReasonUpdate,
    AdminFeedbackStats,
    AdminUniversityItem,
    AdminUniversityUpdate,
    AdminUserItem,
    AdminUserUpdate,
    ModelConfigCreate,
    ModelConfigItem,
    ModelConfigUpdate,
    SystemConfigCreate,
    SystemConfigItem,
    SystemConfigUpdate,
)
from agent.models.university import UniversityInfo
from agent.services.auth import require_admin
from agent.services.model_service import encrypt_api_key
from agent.services.session import get_session_manager
from agent.services.university import get_university_by_id, list_universities
from agent.models.session import ToolCallDetail

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])

VALUE_TYPES = {"string", "number", "boolean", "json", "array"}
ANNOUNCEMENT_STATUSES = {"draft", "published", "offline"}
USER_ROLES = {"user", "admin", "super_admin", "guest"}
USER_STATUSES = {"active", "disabled"}


def _utc_now() -> int:
    return int(time.time())


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ========== 系统配置 ==========

def _validate_config_value(value: str, value_type: str):
    """按 value_type 简单校验 value 字符串，避免存入脏数据破坏消费方"""
    try:
        if value_type == "number":
            float(value)
        elif value_type == "boolean":
            if value.lower() not in ("true", "false"):
                raise ValueError("boolean 类型值必须为 true/false")
        elif value_type in ("json", "array"):
            parsed = json.loads(value)
            if value_type == "array" and not isinstance(parsed, list):
                raise ValueError("array 类型值必须是 JSON 数组")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"值不符合 {value_type} 类型要求: {exc}") from exc


def _config_item(row) -> SystemConfigItem:
    return SystemConfigItem(
        id=row["id"],
        key=row["key"],
        value=row["value"],
        value_type=row["value_type"],
        group_name=row["group_name"],
        label=row["label"],
        description=row["description"],
        is_public=bool(row["is_public"]),
        created_time=row["created_time"],
        updated_time=row["updated_time"],
    )


@router.get("/configs", response_model=list[SystemConfigItem])
def list_configs():
    rows = get_db().execute(
        "SELECT * FROM system_configs ORDER BY group_name, key"
    ).fetchall()
    return [_config_item(row) for row in rows]


@router.post("/configs", response_model=SystemConfigItem, status_code=201)
def create_config(payload: SystemConfigCreate):
    if payload.value_type not in VALUE_TYPES:
        raise _bad_request(ValueError(f"不支持的 value_type: {payload.value_type}"))
    if payload.value:
        try:
            _validate_config_value(payload.value, payload.value_type)
        except ValueError as exc:
            raise _bad_request(exc)
    db = get_db()
    if db.execute("SELECT 1 FROM system_configs WHERE key = ?", (payload.key,)).fetchone():
        raise _bad_request(ValueError(f"配置键已存在: {payload.key}"))
    config_id = str(uuid.uuid4())
    now = _utc_now()
    try:
        db.execute(
            "INSERT INTO system_configs (id, key, value, value_type, group_name, label, description, is_public, created_time, updated_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                config_id,
                payload.key,
                payload.value,
                payload.value_type,
                payload.group_name,
                payload.label,
                payload.description,
                1 if payload.is_public else 0,
                now,
                now,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _bad_request(ValueError(f"配置键已存在: {payload.key}")) from exc
    row = db.execute("SELECT * FROM system_configs WHERE id = ?", (config_id,)).fetchone()
    return _config_item(row)


@router.put("/configs/{config_id}", response_model=SystemConfigItem)
def update_config(config_id: str, payload: SystemConfigUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM system_configs WHERE id = ?", (config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="配置不存在")
    value_type = payload.value_type if payload.value_type is not None else row["value_type"]
    if value_type is not None and value_type not in VALUE_TYPES:
        raise _bad_request(ValueError(f"不支持的 value_type: {value_type}"))
    value = payload.value if payload.value is not None else row["value"]
    if value and value_type:
        try:
            _validate_config_value(value, value_type)
        except ValueError as exc:
            raise _bad_request(exc)
    db.execute(
        "UPDATE system_configs SET value = ?, value_type = ?, group_name = ?, label = ?, description = ?, "
        "is_public = ?, updated_time = ? WHERE id = ?",
        (
            value,
            value_type,
            payload.group_name if payload.group_name is not None else row["group_name"],
            payload.label if payload.label is not None else row["label"],
            payload.description if payload.description is not None else row["description"],
            (1 if payload.is_public else 0) if payload.is_public is not None else row["is_public"],
            _utc_now(),
            config_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM system_configs WHERE id = ?", (config_id,)).fetchone()
    return _config_item(updated)


@router.delete("/configs/{config_id}", status_code=204)
def delete_config(config_id: str):
    db = get_db()
    if not db.execute("SELECT 1 FROM system_configs WHERE id = ?", (config_id,)).fetchone():
        raise HTTPException(status_code=404, detail="配置不存在")
    db.execute("DELETE FROM system_configs WHERE id = ?", (config_id,))
    db.commit()


# ========== 模型配置 ==========

def _model_item(row) -> ModelConfigItem:
    capabilities = {}
    if row["capabilities"]:
        try:
            capabilities = json.loads(row["capabilities"])
        except Exception:
            logger.warning(f"模型 [{row['model_id']}] capabilities JSON 解析失败: {row['capabilities']}")
    return ModelConfigItem(
        id=row["id"],
        name=row["name"],
        model_type=row["model_type"],
        provider=row["provider"],
        model_id=row["model_id"],
        has_api_key=bool(row["api_key"]),
        base_url=row["base_url"],
        api_prefix=row["api_prefix"],
        is_enabled=bool(row["is_enabled"]),
        priority=row["priority"],
        max_tokens=row["max_tokens"],
        temperature=row["temperature"],
        capabilities=capabilities,
        created_time=row["created_time"],
        updated_time=row["updated_time"],
    )


@router.get("/models", response_model=list[ModelConfigItem])
def list_models_config():
    rows = get_db().execute(
        "SELECT * FROM models_configs ORDER BY model_type, priority"
    ).fetchall()
    return [_model_item(row) for row in rows]


@router.post("/models", response_model=ModelConfigItem, status_code=201)
def create_model_config(payload: ModelConfigCreate):
    db = get_db()
    if db.execute(
        "SELECT 1 FROM models_configs WHERE model_id = ? AND model_type = ?",
        (payload.model_id, payload.model_type),
    ).fetchone():
        raise _bad_request(ValueError(f"同类型下模型ID已存在: {payload.model_id}"))
    model_id = str(uuid.uuid4())
    now = _utc_now()
    try:
        db.execute(
            "INSERT INTO models_configs (id, name, model_type, provider, model_id, api_key, base_url, api_prefix, "
            "is_enabled, priority, max_tokens, temperature, capabilities, created_time, updated_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                model_id,
                payload.name,
                payload.model_type,
                payload.provider,
                payload.model_id,
                encrypt_api_key(payload.api_key) if payload.api_key else None,
                payload.base_url,
                payload.api_prefix,
                1 if payload.is_enabled else 0,
                payload.priority,
                payload.max_tokens,
                payload.temperature,
                json.dumps(payload.capabilities, ensure_ascii=False) if payload.capabilities is not None else None,
                now,
                now,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _bad_request(ValueError("模型配置保存失败")) from exc
    row = db.execute("SELECT * FROM models_configs WHERE id = ?", (model_id,)).fetchone()
    return _model_item(row)


@router.put("/models/{model_config_id}", response_model=ModelConfigItem)
def update_model_config(model_config_id: str, payload: ModelConfigUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM models_configs WHERE id = ?", (model_config_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    db.execute(
        "UPDATE models_configs SET name = ?, model_type = ?, provider = ?, model_id = ?, api_key = ?, "
        "base_url = ?, api_prefix = ?, is_enabled = ?, priority = ?, max_tokens = ?, temperature = ?, "
        "capabilities = ?, updated_time = ? WHERE id = ?",
        (
            payload.name if payload.name is not None else row["name"],
            payload.model_type if payload.model_type is not None else row["model_type"],
            payload.provider if payload.provider is not None else row["provider"],
            payload.model_id if payload.model_id is not None else row["model_id"],
            encrypt_api_key(payload.api_key) if payload.api_key else row["api_key"],
            payload.base_url if payload.base_url is not None else row["base_url"],
            payload.api_prefix if payload.api_prefix is not None else row["api_prefix"],
            (1 if payload.is_enabled else 0) if payload.is_enabled is not None else row["is_enabled"],
            payload.priority if payload.priority is not None else row["priority"],
            payload.max_tokens if payload.max_tokens is not None else row["max_tokens"],
            payload.temperature if payload.temperature is not None else row["temperature"],
            json.dumps(payload.capabilities, ensure_ascii=False) if payload.capabilities is not None else row["capabilities"],
            _utc_now(),
            model_config_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM models_configs WHERE id = ?", (model_config_id,)).fetchone()
    return _model_item(updated)


@router.delete("/models/{model_config_id}", status_code=204)
def delete_model_config(model_config_id: str):
    db = get_db()
    if not db.execute("SELECT 1 FROM models_configs WHERE id = ?", (model_config_id,)).fetchone():
        raise HTTPException(status_code=404, detail="模型配置不存在")
    db.execute("DELETE FROM models_configs WHERE id = ?", (model_config_id,))
    db.commit()


# ========== 用户管理 ==========

@router.get("/users", response_model=list[AdminUserItem])
def list_users():
    rows = get_db().execute("SELECT * FROM users ORDER BY created_time").fetchall()
    return [
        AdminUserItem(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            email=row["email"],
            avatar=row["avatar"],
            role=row["role"],
            status=row["status"],
            last_login_time=row["last_login_time"],
            last_login_ip=row["last_login_ip"],
            created_time=row["created_time"],
            updated_time=row["updated_time"],
        )
        for row in rows
    ]


@router.patch("/users/{user_id}", response_model=AdminUserItem)
def update_user(user_id: str, payload: AdminUserUpdate, current_user: dict = Depends(require_admin)):
    if payload.role is not None and payload.role not in USER_ROLES:
        raise _bad_request(ValueError(f"不支持的角色: {payload.role}"))
    # 游客角色仅超级管理员可设置
    if payload.role == "guest" and current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可将账号设为游客")
    if payload.status is not None and payload.status not in USER_STATUSES:
        raise _bad_request(ValueError(f"不支持的状态: {payload.status}"))
    if user_id == current_user["id"]:
        raise _bad_request(ValueError("不能修改自己的角色或状态，防止误操作导致失去管理权限"))
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.execute(
        "UPDATE users SET role = ?, status = ?, updated_time = ? WHERE id = ?",
        (
            payload.role if payload.role is not None else row["role"],
            payload.status if payload.status is not None else row["status"],
            _utc_now(),
            user_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return AdminUserItem(
        id=updated["id"],
        username=updated["username"],
        display_name=updated["display_name"],
        email=updated["email"],
        avatar=updated["avatar"],
        role=updated["role"],
        status=updated["status"],
        last_login_time=updated["last_login_time"],
        last_login_ip=updated["last_login_ip"],
        created_time=updated["created_time"],
        updated_time=updated["updated_time"],
    )


# ========== 公告管理 ==========

def _announcement_item(row) -> AdminAnnouncementItem:
    return AdminAnnouncementItem(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        status=row["status"],
        publish_time=row["publish_time"],
        is_pinned=bool(row["is_pinned"]),
        popup_start_time=row["popup_start_time"],
        popup_end_time=row["popup_end_time"],
        created_by=row["created_by"],
        created_time=row["created_time"],
        updated_time=row["updated_time"],
    )


@router.get("/announcements", response_model=list[AdminAnnouncementItem])
def list_announcements_admin():
    rows = get_db().execute(
        "SELECT * FROM announcements ORDER BY is_pinned DESC, COALESCE(publish_time, created_time) DESC"
    ).fetchall()
    return [_announcement_item(row) for row in rows]


@router.post("/announcements", response_model=AdminAnnouncementItem, status_code=201)
def create_announcement(payload: AdminAnnouncementCreate, current_user: dict = Depends(require_admin)):
    if payload.status not in ANNOUNCEMENT_STATUSES:
        raise _bad_request(ValueError(f"不支持的公告状态: {payload.status}"))
    announcement_id = str(uuid.uuid4())
    now = _utc_now()
    db = get_db()
    db.execute(
        "INSERT INTO announcements (id, title, content, status, publish_time, is_pinned, popup_start_time, popup_end_time, created_by, created_time, updated_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            announcement_id,
            payload.title,
            payload.content,
            payload.status,
            payload.publish_time,
            1 if payload.is_pinned else 0,
            payload.popup_start_time,
            payload.popup_end_time,
            current_user["id"],
            now,
            now,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
    return _announcement_item(row)


@router.put("/announcements/{announcement_id}", response_model=AdminAnnouncementItem)
def update_announcement(announcement_id: str, payload: AdminAnnouncementUpdate):
    if payload.status is not None and payload.status not in ANNOUNCEMENT_STATUSES:
        raise _bad_request(ValueError(f"不支持的公告状态: {payload.status}"))
    db = get_db()
    row = db.execute("SELECT * FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在")
    db.execute(
        "UPDATE announcements SET title = ?, content = ?, status = ?, publish_time = ?, is_pinned = ?, "
        "popup_start_time = ?, popup_end_time = ?, updated_time = ? WHERE id = ?",
        (
            payload.title if payload.title is not None else row["title"],
            payload.content if payload.content is not None else row["content"],
            payload.status if payload.status is not None else row["status"],
            payload.publish_time if payload.publish_time is not None else row["publish_time"],
            (1 if payload.is_pinned else 0) if payload.is_pinned is not None else row["is_pinned"],
            payload.popup_start_time if payload.popup_start_time is not None else row["popup_start_time"],
            payload.popup_end_time if payload.popup_end_time is not None else row["popup_end_time"],
            _utc_now(),
            announcement_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
    return _announcement_item(updated)


@router.delete("/announcements/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: str):
    db = get_db()
    if not db.execute("SELECT 1 FROM announcements WHERE id = ?", (announcement_id,)).fetchone():
        raise HTTPException(status_code=404, detail="公告不存在")
    db.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    db.execute("DELETE FROM announcement_reads WHERE announcement_id = ?", (announcement_id,))
    db.commit()


# ========== 反馈管理 (message_feedbacks / feedback_reasons) ==========

FEEDBACK_TYPES = {"like", "dislike"}
REASON_FEEDBACK_TYPES = {"like", "dislike", "all"}
REASON_STATUSES = {"active", "disabled"}


def _parse_reason_codes(raw) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _message_text_preview(db, message_id: str, max_len: int = 200) -> Optional[str]:
    """提取消息的文本内容（type='text' 的内容块按序拼接），超长截断"""
    rows = db.execute(
        "SELECT content FROM message_contents WHERE message_id = ? AND type = 'text' "
        "ORDER BY sort_order",
        (message_id,),
    ).fetchall()
    text = "\n".join(row["content"] or "" for row in rows).strip()
    if not text:
        return None
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _feedback_like_clause(reason_code: str) -> tuple[str, list]:
    """reason_codes 为 JSON 数组文本，用 json_each 精确匹配 code"""
    return "EXISTS (SELECT 1 FROM json_each(f.reason_codes) je WHERE je.value = ?)", [reason_code]


@router.get("/feedbacks/stats", response_model=AdminFeedbackStats)
def feedback_stats():
    """反馈统计：总数 / 点赞数 / 拉踩数 / 参与用户数 / 原因分布"""
    db = get_db()
    rows = db.execute(
        "SELECT feedback_type, reason_codes, user_id FROM message_feedbacks WHERE status = 'active'"
    ).fetchall()
    like_count = 0
    dislike_count = 0
    user_ids = set()
    reason_counter: dict[str, int] = {}
    for row in rows:
        if row["feedback_type"] == "like":
            like_count += 1
        elif row["feedback_type"] == "dislike":
            dislike_count += 1
        if row["user_id"]:
            user_ids.add(row["user_id"])
        for code in _parse_reason_codes(row["reason_codes"]):
            reason_counter[code] = reason_counter.get(code, 0) + 1
    # 原因 label 从字典取，字典中已不存在的原因保留 code 原样展示
    reason_rows = db.execute("SELECT code, label, feedback_type FROM feedback_reasons").fetchall()
    reason_labels = {row["code"]: (row["label"], row["feedback_type"]) for row in reason_rows}
    reason_stats = [
        AdminFeedbackReasonStat(
            code=code,
            label=reason_labels.get(code, (None, None))[0] or code,
            feedback_type=reason_labels.get(code, (None, None))[1],
            count=count,
        )
        for code, count in sorted(reason_counter.items(), key=lambda item: -item[1])
    ]
    return AdminFeedbackStats(
        total_count=len(rows),
        like_count=like_count,
        dislike_count=dislike_count,
        user_count=len(user_ids),
        reason_stats=reason_stats,
    )


@router.get("/feedbacks", response_model=list[AdminFeedbackItem])
def list_feedbacks(
    feedback_type: str = Query(default=None, description="按类型过滤：like | dislike"),
    reason_code: str = Query(default=None, description="按原因编码过滤（含该原因的记录）"),
    status: str = Query(default="active", description="记录状态：active | revoked | all"),
):
    """反馈记录列表：联表返回用户名 / 会话标题 / 被评价消息文本预览，按提交时间倒序"""
    if feedback_type is not None and feedback_type not in FEEDBACK_TYPES:
        raise _bad_request(ValueError(f"不支持的反馈类型: {feedback_type}"))
    if status not in ("active", "revoked", "all"):
        raise _bad_request(ValueError(f"不支持的记录状态: {status}"))
    db = get_db()
    where = ["1 = 1"]
    params: list = []
    if status != "all":
        where.append("f.status = ?")
        params.append(status)
    if feedback_type:
        where.append("f.feedback_type = ?")
        params.append(feedback_type)
    if reason_code:
        clause, clause_params = _feedback_like_clause(reason_code)
        where.append(clause)
        params.extend(clause_params)
    rows = db.execute(
        "SELECT f.*, m.session_id AS session_id, s.title AS session_title, u.username, u.display_name "
        "FROM message_feedbacks f "
        "LEFT JOIN messages m ON m.id = f.message_id "
        "LEFT JOIN sessions s ON s.id = m.session_id "
        "LEFT JOIN users u ON u.id = f.user_id "
        f"WHERE {' AND '.join(where)} ORDER BY f.created_time DESC",
        params,
    ).fetchall()
    items = []
    for row in rows:
        items.append(AdminFeedbackItem(
            id=row["id"],
            message_id=row["message_id"],
            session_id=row["session_id"],
            session_title=row["session_title"],
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            feedback_type=row["feedback_type"],
            reason_codes=_parse_reason_codes(row["reason_codes"]),
            comment=row["comment"],
            message_preview=_message_text_preview(db, row["message_id"]),
            status=row["status"],
            created_time=row["created_time"],
            updated_time=row["updated_time"],
        ))
    return items


@router.get("/feedbacks/reasons", response_model=list[AdminFeedbackReasonItem])
def list_feedback_reasons_admin():
    """原因字典全量列表（含停用项），used_count 为被 active 反馈引用的次数"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM feedback_reasons ORDER BY feedback_type, sort_order, code"
    ).fetchall()
    usage_rows = db.execute(
        "SELECT je.value AS code, COUNT(*) AS cnt FROM message_feedbacks f, json_each(f.reason_codes) je "
        "WHERE f.status = 'active' GROUP BY je.value"
    ).fetchall()
    usage = {row["code"]: row["cnt"] for row in usage_rows}
    return [
        AdminFeedbackReasonItem(
            id=row["id"],
            code=row["code"],
            feedback_type=row["feedback_type"],
            label=row["label"],
            description=row["description"],
            status=row["status"],
            sort_order=row["sort_order"],
            used_count=usage.get(row["code"], 0),
            created_time=row["created_time"],
            updated_time=row["updated_time"],
        )
        for row in rows
    ]


@router.post("/feedbacks/reasons", response_model=AdminFeedbackReasonItem, status_code=201)
def create_feedback_reason(payload: AdminFeedbackReasonCreate):
    if payload.feedback_type not in REASON_FEEDBACK_TYPES:
        raise _bad_request(ValueError(f"不支持的适用类型: {payload.feedback_type}"))
    if payload.status not in REASON_STATUSES:
        raise _bad_request(ValueError(f"不支持的状态: {payload.status}"))
    db = get_db()
    if db.execute("SELECT 1 FROM feedback_reasons WHERE code = ?", (payload.code,)).fetchone():
        raise _bad_request(ValueError(f"原因编码已存在: {payload.code}"))
    reason_id = str(uuid.uuid4())
    now = _utc_now()
    db.execute(
        "INSERT INTO feedback_reasons (id, code, feedback_type, label, description, status, sort_order, created_time, updated_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            reason_id, payload.code, payload.feedback_type, payload.label,
            payload.description, payload.status, payload.sort_order, now, now,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM feedback_reasons WHERE id = ?", (reason_id,)).fetchone()
    return AdminFeedbackReasonItem(
        id=row["id"], code=row["code"], feedback_type=row["feedback_type"], label=row["label"],
        description=row["description"], status=row["status"], sort_order=row["sort_order"],
        used_count=0, created_time=row["created_time"], updated_time=row["updated_time"],
    )


@router.put("/feedbacks/reasons/{reason_id}", response_model=AdminFeedbackReasonItem)
def update_feedback_reason(reason_id: str, payload: AdminFeedbackReasonUpdate):
    if payload.feedback_type is not None and payload.feedback_type not in REASON_FEEDBACK_TYPES:
        raise _bad_request(ValueError(f"不支持的适用类型: {payload.feedback_type}"))
    if payload.status is not None and payload.status not in REASON_STATUSES:
        raise _bad_request(ValueError(f"不支持的状态: {payload.status}"))
    db = get_db()
    row = db.execute("SELECT * FROM feedback_reasons WHERE id = ?", (reason_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="反馈原因不存在")
    db.execute(
        "UPDATE feedback_reasons SET feedback_type = ?, label = ?, description = ?, status = ?, "
        "sort_order = ?, updated_time = ? WHERE id = ?",
        (
            payload.feedback_type if payload.feedback_type is not None else row["feedback_type"],
            payload.label if payload.label is not None else row["label"],
            payload.description if payload.description is not None else row["description"],
            payload.status if payload.status is not None else row["status"],
            payload.sort_order if payload.sort_order is not None else row["sort_order"],
            _utc_now(),
            reason_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM feedback_reasons WHERE id = ?", (reason_id,)).fetchone()
    usage = db.execute(
        "SELECT COUNT(*) AS cnt FROM message_feedbacks f, json_each(f.reason_codes) je "
        "WHERE f.status = 'active' AND je.value = ?",
        (updated["code"],),
    ).fetchone()
    return AdminFeedbackReasonItem(
        id=updated["id"], code=updated["code"], feedback_type=updated["feedback_type"],
        label=updated["label"], description=updated["description"], status=updated["status"],
        sort_order=updated["sort_order"], used_count=usage["cnt"],
        created_time=updated["created_time"], updated_time=updated["updated_time"],
    )


@router.delete("/feedbacks/reasons/{reason_id}", status_code=204)
def delete_feedback_reason(reason_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM feedback_reasons WHERE id = ?", (reason_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="反馈原因不存在")
    used = db.execute(
        "SELECT COUNT(*) AS cnt FROM message_feedbacks f, json_each(f.reason_codes) je "
        "WHERE f.status = 'active' AND je.value = ?",
        (row["code"],),
    ).fetchone()
    if used["cnt"] > 0:
        raise _bad_request(ValueError(f"原因「{row['label'] or row['code']}」已被 {used['cnt']} 条反馈引用，请改为停用"))
    db.execute("DELETE FROM feedback_reasons WHERE id = ?", (reason_id,))
    db.commit()


@router.get("/feedbacks/{feedback_id}/context", response_model=AdminFeedbackContext)
def feedback_context(feedback_id: str):
    """查看反馈上下文：复用用户侧会话详情构建逻辑，返回与用户看到的一模一样的数据"""
    db = get_db()
    fb = db.execute(
        "SELECT f.message_id, m.session_id FROM message_feedbacks f "
        "LEFT JOIN messages m ON m.id = f.message_id "
        "WHERE f.id = ?",
        (feedback_id,),
    ).fetchone()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈记录不存在")
    if not fb["session_id"]:
        raise HTTPException(status_code=404, detail="被评价消息不存在或所属会话已删除")
    detail = get_session_manager().get_session_admin(fb["session_id"])
    if not detail:
        raise HTTPException(status_code=404, detail=f"会话不存在: {fb['session_id']}")
    return AdminFeedbackContext(
        feedback_message_id=fb["message_id"],
        session=detail,
    )


@router.get("/tool-calls", response_model=list[ToolCallDetail])
def admin_tool_calls(message_id: str = Query(..., description="消息ID")):
    """工具详情懒加载（管理端共用用户侧逻辑，不做会话归属校验）"""
    return get_session_manager().get_tool_calls_by_message(message_id)


# ========== 高校信息 (universities) ==========

# universities 可编辑字段：JSON 数组字段（aliases / tags）单独序列化入库
_UNIVERSITY_JSON_FIELDS = {"aliases", "tags"}


def _university_item(info: dict) -> AdminUniversityItem:
    return AdminUniversityItem(
        **info,
        has_logo=bool(info.get("logo_url")),
    )


@router.get("/universities", response_model=list[AdminUniversityItem])
def admin_list_universities():
    """全部高校基础信息列表（不含实力数据），前端本地筛选与分页"""
    return [_university_item(info) for info in list_universities()]


@router.get("/universities/{university_id}", response_model=UniversityInfo)
def admin_get_university(university_id: str):
    """高校详情（含排名 / 双一流建设学科 / 学科评估）"""
    info = get_university_by_id(university_id)
    if not info:
        raise HTTPException(status_code=404, detail="高校不存在")
    return UniversityInfo(**info)


@router.patch("/universities/{university_id}", response_model=UniversityInfo)
def admin_update_university(university_id: str, payload: AdminUniversityUpdate):
    db = get_db()
    row = db.execute("SELECT id, name FROM universities WHERE id = ?", (university_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="高校不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        new_name = (updates["name"] or "").strip()
        if not new_name:
            raise _bad_request(ValueError("高校名称不能为空"))
        exists = db.execute(
            "SELECT 1 FROM universities WHERE name = ? AND id != ?",
            (new_name, university_id),
        ).fetchone()
        if exists:
            raise _bad_request(ValueError(f"高校名称「{new_name}」已存在"))
        updates["name"] = new_name

    assignments, params = [], []
    for field, value in updates.items():
        if field in _UNIVERSITY_JSON_FIELDS:
            value = json.dumps(value, ensure_ascii=False)
        assignments.append(f"{field} = ?")
        params.append(value)
    assignments.append("updated_time = ?")
    params.append(_utc_now())
    params.append(university_id)
    db.execute(
        f"UPDATE universities SET {', '.join(assignments)} WHERE id = ?",
        params,
    )
    db.commit()

    info = get_university_by_id(university_id)
    return UniversityInfo(**info)
