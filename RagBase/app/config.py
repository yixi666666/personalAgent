import os
from pathlib import Path
from dynaconf import Dynaconf


_CONFIG = None

_BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _BASE_DIR / "config.yaml"

_settings = Dynaconf(
    settings_files=[str(_CONFIG_PATH)],
    load_dotenv=True,
    dotenv_path=str(_BASE_DIR / ".env"),
)


def load_config():
    """返回配置对象，支持字典式访问"""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    _CONFIG = _settings
    return _CONFIG


def get_config():
    return load_config()


def get_upload_token() -> str:
    token = _settings.get("upload", {}).get("token", "")
    if not token:
        raise ValueError("配置文件中 upload.token 未设置。")
    return token
