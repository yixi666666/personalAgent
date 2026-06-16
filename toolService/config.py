import yaml
import os
from typing import Any, Optional


_config_instance: Optional["Config"] = None


class Config:
    def __init__(self, config_path: str = None, tools_path: str = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 读取服务基础配置
        if config_path is None:
            config_path = os.path.join(base_dir, "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

        # 读取工具配置
        if tools_path is None:
            tools_path = os.path.join(base_dir, "tools.yaml")
        with open(tools_path, "r", encoding="utf-8") as f:
            self._tools_data = yaml.safe_load(f)

    @property
    def server(self) -> dict:
        return self._data.get("server", {})

    @property
    def server_host(self) -> str:
        return self.server.get("host", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return self.server.get("port", 8003)

    @property
    def logging(self) -> dict:
        return self._data.get("logging", {})

    @property
    def log_level(self) -> str:
        return self.logging.get("level", "INFO")

    @property
    def log_format(self) -> str:
        return self.logging.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    @property
    def internal_tools(self) -> list[dict]:
        """自研工具配置列表，每项含 name 和 handler"""
        return self._tools_data.get("internal_tools", [])

    @property
    def local_mcp(self) -> list[dict]:
        """本地MCP工具配置列表，每项含 name/command/args/transport/env/workdir/retry"""
        return self._tools_data.get("local_mcp", [])

    @property
    def remote_mcp(self) -> list[dict]:
        """远程MCP工具配置列表，每项含 name/url/auth/max_retries"""
        return self._tools_data.get("remote_mcp", [])

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
