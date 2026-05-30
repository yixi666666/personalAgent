import yaml
import os
from pathlib import Path
from typing import Any


_config_instance = None


class Config:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
        return self.server.get("port", 8001)

    @property
    def server_reload(self) -> bool:
        return self.server.get("reload", True)

    @property
    def model(self) -> dict:
        return self._data.get("model", {})

    @property
    def model_name(self) -> str:
        return self.model.get("name", "Arch-Agent-3B")

    @property
    def model_base_url(self) -> str:
        return self.model.get("base_url", "http://localhost:8000")

    @property
    def model_max_tokens(self) -> int:
        return self.model.get("max_tokens", 2048)

    @property
    def model_temperature(self) -> float:
        return self.model.get("temperature", 0.7)

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
    def tools(self) -> dict:
        return self._data.get("tools", {})

    @property
    def tools_enabled(self) -> bool:
        return self.tools.get("enabled", True)

    @property
    def tools_timeout(self) -> int:
        return self.tools.get("timeout", 30)

    @property
    def providers(self) -> dict:
        return self._data.get("providers", {})

    def get_provider_config(self, provider_name: str) -> dict:
        return self.providers.get(provider_name, {})

    def get_all_model_providers(self) -> list[dict]:
        result = [
            {
                "provider": "local",
                "name": self.model_name,
                "display_name": "本地模型",
                "base_url": self.model_base_url,
                "api_prefix": "/v1",
                "max_tokens": self.model_max_tokens,
                "temperature": self.model_temperature,
                "api_key": None,
            }
        ]
        for provider_name, provider_cfg in self.providers.items():
            result.append(
                {
                    "provider": provider_name,
                    "name": provider_cfg.get("name", ""),
                    "display_name": provider_cfg.get("display_name", provider_name),
                    "base_url": provider_cfg.get("base_url", ""),
                    "api_prefix": provider_cfg.get("api_prefix", "/v1"),
                    "max_tokens": provider_cfg.get("max_tokens", 2048),
                    "temperature": provider_cfg.get("temperature", 0.7),
                    "api_key": provider_cfg.get("api_key"),
                }
            )
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
