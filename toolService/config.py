import yaml
import os
from typing import Any, Optional


_config_instance: Optional["Config"] = None


class Config:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "config.yaml",
            )
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

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
    def mcp_servers(self) -> dict:
        return self._data.get("mcp_servers", {})

    @property
    def tools(self) -> dict:
        return self._data.get("tools", {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
