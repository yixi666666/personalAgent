"""模型配置服务：模型元数据唯一来源为数据库。

- chat 模型：models_configs 表 model_type='chat' 且 is_enabled=1 的记录，按 priority 升序
- 默认模型：system_configs 表 key='llm.default_model'（存 model_id）
- embedding 模型：models_configs 表 model_type='embedding' 且 is_enabled=1 的记录
- api_key 使用 Fernet 对称加密存储，主密钥从环境变量 MODEL_ENCRYPTION_KEY 读取（agent/.env）
"""

import json
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from agent.database import get_db

logger = logging.getLogger(__name__)

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        master_key = os.environ.get("MODEL_ENCRYPTION_KEY")
        if not master_key:
            raise ValueError(
                "未配置 MODEL_ENCRYPTION_KEY，无法解密模型 api_key（应在 agent/.env 中配置）"
            )
        _fernet = Fernet(master_key.encode())
    return _fernet


def encrypt_api_key(plain_key: str) -> str:
    """明文 api_key 加密为可入库的密文字符串"""
    return _get_fernet().encrypt(plain_key.encode()).decode()


def decrypt_api_key(cipher_key: str) -> str:
    """解密 models_configs.api_key 中的密文"""
    return _get_fernet().decrypt(cipher_key.encode()).decode()


def _row_to_provider(row) -> dict:
    """将 models_configs 行转换为原 provider dict 结构（对齐历史调用方字段）"""
    capabilities = json.loads(row["capabilities"]) if row["capabilities"] else {}
    api_key = None
    if row["api_key"]:
        try:
            api_key = decrypt_api_key(row["api_key"])
        except InvalidToken:
            logger.error(
                f"模型 [{row['model_id']}] api_key 解密失败（MODEL_ENCRYPTION_KEY 不匹配），请重新加密入库"
            )
    return {
        "provider": row["provider"] or "",
        "name": row["model_id"] or "",
        "display_name": row["name"] or row["model_id"] or "",
        "base_url": row["base_url"] or "",
        "api_prefix": row["api_prefix"] if row["api_prefix"] is not None else "",
        "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 2048,
        "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
        "api_key": api_key,
        "supports_tools": bool(capabilities.get("supports_tools", True)),
        "deep_thinking": bool(capabilities.get("deep_thinking", False)),
        "web_search": bool(capabilities.get("web_search", False)),
        "structured_output": bool(capabilities.get("structured_output", False)),
        "multimodal": bool(capabilities.get("multimodal", False)),
        "streaming": bool(capabilities.get("streaming", True)),
        "stop_anytime": bool(capabilities.get("stop_anytime", True)),
        "context_window": capabilities.get("context_window", 4096),
    }


def get_chat_providers() -> list[dict]:
    """全部启用的 chat 模型配置，按 priority 升序"""
    rows = get_db().execute(
        "SELECT * FROM models_configs WHERE model_type = 'chat' AND is_enabled = 1 "
        "ORDER BY priority ASC"
    ).fetchall()
    return [_row_to_provider(row) for row in rows]


def resolve_chat_provider(model_id: str) -> dict:
    """按 model_id 解析启用的 chat 模型配置，未找到抛 ValueError"""
    for provider in get_chat_providers():
        if provider["name"] == model_id:
            return provider
    raise ValueError(f"未找到可用模型: {model_id}")


def get_default_model() -> Optional[str]:
    """默认模型（model_id），来自 system_configs 'llm.default_model'"""
    row = get_db().execute(
        "SELECT value FROM system_configs WHERE key = 'llm.default_model'"
    ).fetchone()
    return row["value"] if row else None


def get_embedding_provider() -> dict:
    """启用的 embedding 模型配置：优先匹配 system_configs 'embedding.default_model'"""
    rows = get_db().execute(
        "SELECT * FROM models_configs WHERE model_type = 'embedding' AND is_enabled = 1 "
        "ORDER BY priority ASC"
    ).fetchall()
    if not rows:
        raise ValueError("数据库中未配置启用的 embedding 模型（models_configs.model_type='embedding'）")
    row_cfg = get_db().execute(
        "SELECT value FROM system_configs WHERE key = 'embedding.default_model'"
    ).fetchone()
    default_model = row_cfg["value"] if row_cfg else None
    for row in rows:
        if (row["model_id"] or "") == default_model:
            return _row_to_provider(row)
    return _row_to_provider(rows[0])
