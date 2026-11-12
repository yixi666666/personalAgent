"""管理端路由：系统配置 / 模型配置 / 用户管理 / 公告管理。

- 全部接口要求 admin / super_admin 角色（router 级 require_admin 依赖）
- 时间字段：UTC 秒，应用层填充
- 模型 api_key 复用 model_service 的 Fernet 加密，明文仅在请求中出现，不回传
"""

import json
import logging
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from agent.database import get_db
from agent.models.admin import (
    AdminAnnouncementCreate,
    AdminAnnouncementItem,
    AdminAnnouncementUpdate,
    AdminUserItem,
    AdminUserUpdate,
    ModelConfigCreate,
    ModelConfigItem,
    ModelConfigUpdate,
    SystemConfigCreate,
    SystemConfigItem,
    SystemConfigUpdate,
)
from agent.services.auth import require_admin
from agent.services.model_service import encrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])

VALUE_TYPES = {"string", "number", "boolean", "json", "array"}
ANNOUNCEMENT_STATUSES = {"draft", "published", "offline"}
USER_ROLES = {"user", "admin", "super_admin"}
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
