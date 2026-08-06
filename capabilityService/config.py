import os
import yaml
from typing import Any, Optional
from dynaconf import Dynaconf


_config_instance: Optional["Config"] = None

_base_dir = os.path.dirname(os.path.abspath(__file__))

_settings = Dynaconf(
    settings_files=[os.path.join(_base_dir, "config.yaml")],
    load_dotenv=True,
    dotenv_path=os.path.join(_base_dir, ".env"),
)

# 读取工具配置（独立的 tools.yaml，不含敏感信息）
_tools_path = os.path.join(_base_dir, "tools.yaml")
with open(_tools_path, "r", encoding="utf-8") as f:
    _tools_data = yaml.safe_load(f)


class Config:
    @property
    def server(self) -> dict:
        return _settings.get("server", {})

    @property
    def server_host(self) -> str:
        return _settings.get("server", {}).get("host", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return _settings.get("server", {}).get("port", 8003)

    @property
    def logging(self) -> dict:
        return _settings.get("logging", {})

    @property
    def log_level(self) -> str:
        return _settings.get("logging", {}).get("level", "INFO")

    @property
    def log_format(self) -> str:
        return _settings.get("logging", {}).get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    @property
    def internal_tools(self) -> list[dict]:
        """自研工具配置列表，每项含 name 和 handler"""
        return _tools_data.get("internal_tools", [])

    @property
    def local_mcp(self) -> list[dict]:
        """本地MCP工具配置列表，每项含 name/command/args/transport/env/workdir/retry"""
        return _tools_data.get("local_mcp", [])

    @property
    def remote_mcp(self) -> list[dict]:
        """远程MCP工具配置列表，每项含 name/url/auth/max_retries"""
        return _tools_data.get("remote_mcp", [])

    def get(self, key: str, default: Any = None) -> Any:
        return _settings.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
