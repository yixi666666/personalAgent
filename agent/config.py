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
        return self.server.get("port", 8002)

    @property
    def server_reload(self) -> bool:
        return self.server.get("reload", True)

    @property
    def default_model(self) -> str:
        return self._data.get("default_model", "xop3qwen1b7")

    @property
    def database(self) -> dict:
        return self._data.get("database", {})

    @property
    def database_path(self) -> str:
        path = self.database.get("path", "./data/chatAgent.sqlite")
        db_dir = os.path.dirname(path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        return path

    @property
    def database_echo(self) -> bool:
        return self.database.get("echo", False)

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
    def toolservice(self) -> dict:
        return self._data.get("toolservice", {})

    @property
    def toolservice_url(self) -> str:
        return self.toolservice.get("url", "http://localhost:8003")

    @property
    def toolservice_refresh_interval(self) -> int:
        return self.toolservice.get("refresh_interval", 300)

    @property
    def tool_call_timeout(self) -> int:
        return self.toolservice.get("call_timeout", 10)

    @property
    def providers(self) -> dict:
        return self._data.get("providers", {})

    def get_all_model_providers(self) -> list[dict]:
        result = []
        for provider_name, provider_cfg in self.providers.items():
            result.append({
                "provider": provider_name,
                "name": provider_cfg.get("name", ""),
                "display_name": provider_cfg.get("display_name", provider_name),
                "base_url": provider_cfg.get("base_url", ""),
                "api_prefix": provider_cfg.get("api_prefix", "/v1"),
                "max_tokens": provider_cfg.get("max_tokens", 2048),
                "temperature": provider_cfg.get("temperature", 0.7),
                "api_key": provider_cfg.get("api_key"),
                "supports_tools": provider_cfg.get("supports_tools", True),
            })
        return result

    def resolve_model_provider(self, model_name: str) -> dict:
        for mp in self.get_all_model_providers():
            if mp["name"] == model_name:
                return mp
        return self.get_all_model_providers()[0]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
