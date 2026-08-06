import os
from typing import Any, Optional
from dynaconf import Dynaconf


_config_instance: Optional["Config"] = None

_base_dir = os.path.dirname(os.path.abspath(__file__))

_settings = Dynaconf(
    settings_files=[os.path.join(_base_dir, "config.yaml")],
    load_dotenv=True,
    dotenv_path=os.path.join(_base_dir, ".env"),
)


class Config:
    @property
    def server(self) -> dict:
        return _settings.get("server", {})

    @property
    def server_host(self) -> str:
        return _settings.get("server", {}).get("host", "0.0.0.0")

    @property
    def server_port(self) -> int:
        return _settings.get("server", {}).get("port", 8002)

    @property
    def database(self) -> dict:
        return _settings.get("database", {})

    @property
    def database_path(self) -> str:
        path = _settings.get("database", {}).get("path", "./data/chatAgent.sqlite")
        if not os.path.isabs(path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, path)
        db_dir = os.path.dirname(path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        return path

    @property
    def database_echo(self) -> bool:
        return _settings.get("database", {}).get("echo", False)

    @property
    def logging(self) -> dict:
        return _settings.get("logging", {})

    @property
    def log_level(self) -> str:
        return _settings.get("logging", {}).get("level", "INFO")

    @property
    def log_format(self) -> str:
        return _settings.get("logging", {}).get(
            "format", "%(asctime)s - %(name)-20s - %(levelname)s - %(message)s"
        )

    @property
    def capabilityservice(self) -> dict:
        return _settings.get("capabilityservice", {})

    @property
    def capabilityservice_url(self) -> str:
        return _settings.get("capabilityservice", {}).get("url", "http://localhost:8003")

    @property
    def capabilityservice_refresh_interval(self) -> int:
        return _settings.get("capabilityservice", {}).get("refresh_interval", 300)

    @property
    def tool_call_timeout(self) -> int:
        return _settings.get("capabilityservice", {}).get("call_timeout", 10)

    @property
    def providers(self) -> dict:
        return _settings.get("providers", {})

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
                "deep_thinking": provider_cfg.get("deep_thinking", False),
                "web_search": provider_cfg.get("web_search", False),
                "structured_output": provider_cfg.get("structured_output", False),
                "multimodal": provider_cfg.get("multimodal", False),
                "streaming": provider_cfg.get("streaming", True),
                "stop_anytime": provider_cfg.get("stop_anytime", True),
                "context_window": provider_cfg.get("context_window", 4096),
            })
        return result

    def resolve_model_provider(self, model_name: str) -> dict:
        providers = self.get_all_model_providers()
        for mp in providers:
            if mp["name"] == model_name:
                return mp
        raise ValueError(f"未找到模型提供者: {model_name}")

    def get(self, key: str, default: Any = None) -> Any:
        return _settings.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
