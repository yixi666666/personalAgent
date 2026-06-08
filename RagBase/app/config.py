import os
from pathlib import Path

import yaml


_CONFIG = None

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _CONFIG = yaml.safe_load(f)
    return _CONFIG


def get_config() -> dict:
    return load_config()


def get_upload_token() -> str:
    config = get_config()
    token = config.get("upload", {}).get("token", "")
    if not token:
        raise ValueError("配置文件中 upload.token 未设置。")
    return token
