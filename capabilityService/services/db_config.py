import logging
import os
import sqlite3
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# capabilityService/services/db_config.py → 项目根目录上溯两级
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_db_path = os.path.join(_project_root, "data", "chatAgent.sqlite")

# 配置缓存：进程内加载一次，修改数据库配置后需重启服务生效
_cache: Optional[Dict[str, str]] = None

# 加密主密钥与 agent/services/model_service.py 共用（MODEL_ENCRYPTION_KEY，环境变量注入，不存数据库）
_fernet: Optional[Fernet] = None
_fernet_init_failed = False


def _get_fernet() -> Optional[Fernet]:
    global _fernet, _fernet_init_failed
    if _fernet is None and not _fernet_init_failed:
        master_key = os.environ.get("MODEL_ENCRYPTION_KEY", "")
        if not master_key:
            logger.error(
                "未配置 MODEL_ENCRYPTION_KEY，无法解密 system_configs 中的加密配置"
                "（应在 capabilityService/.env 中配置，与 agent/.env 保持一致）"
            )
            _fernet_init_failed = True
            return None
        _fernet = Fernet(master_key.encode())
    return _fernet


def encrypt_value(plain: str) -> str:
    """Fernet 对称加密，用于向 system_configs 写入敏感配置（如 API Key）"""
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("未配置 MODEL_ENCRYPTION_KEY，无法加密")
    return fernet.encrypt(plain.encode()).decode()


def _try_decrypt(value: str) -> str:
    """解密敏感配置；Fernet 令牌固定以 gAAAAA 开头，非密文原样返回"""
    if not value.startswith("gAAAAA"):
        return value
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("未配置 MODEL_ENCRYPTION_KEY，无法解密 system_configs 中的加密配置")
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        raise RuntimeError("system_configs 加密配置解密失败（MODEL_ENCRYPTION_KEY 不匹配），请重新加密入库") from None


def _load_all() -> Dict[str, str]:
    """加载 system_configs 表中所有 tool.* 配置（进程内缓存一次）

    数据库是唯一配置来源：文件缺失或读取失败直接抛错，不做任何静默降级
    """
    global _cache
    if _cache is None:
        if not os.path.isfile(_db_path):
            raise RuntimeError(f"数据库文件不存在: {_db_path}，无法读取 tool.* 配置")
        try:
            conn = sqlite3.connect(_db_path)
            try:
                rows = conn.execute(
                    "SELECT key, value FROM system_configs WHERE key LIKE 'tool.%'"
                ).fetchall()
                _cache = {k: v for k, v in rows if v}
            finally:
                conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f"读取 system_configs 配置失败: {e}") from e
        logger.info(f"已从 system_configs 加载 {len(_cache)} 项 tool.* 配置")
    return _cache


def get_tool_config(key: str, default: str = "") -> str:
    """读取工具配置（数据库 system_configs 表，敏感配置为 Fernet 密文，读取时自动解密）

    key 格式: tool.{name}，如 tool.tavily_api_key
    数据库中未配置的 key 返回空串（由调用方给出未配置提示），不回退环境变量
    """
    value = _load_all().get(key, "")
    if value:
        return _try_decrypt(value)
    return default
