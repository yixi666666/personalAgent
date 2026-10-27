import logging
import os
import secrets
from typing import Any, Optional
from dynaconf import Dynaconf


logger = logging.getLogger(__name__)
_config_instance: Optional["Config"] = None
_auth_cookie_secret: Optional[str] = None

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
    def max_tool_rounds(self) -> int:
        return _settings.get("agent", {}).get("max_tool_rounds", 10)

    @property
    def database(self) -> dict:
        return _settings.get("database", {})

    @property
    def database_path(self) -> str:
        path = _settings.get("database", {}).get("path", "./data/chatAgent.sqlite")
        if not os.path.isabs(path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, path)
        return path

    @property
    def database_echo(self) -> bool:
        return _settings.get("database", {}).get("echo", False)

    @property
    def auth_cookie_secret(self) -> str:
        global _auth_cookie_secret
        if _auth_cookie_secret is None:
            configured_secret = os.environ.get("AUTH_COOKIE_SECRET")
            if configured_secret:
                _auth_cookie_secret = configured_secret
            else:
                _auth_cookie_secret = secrets.token_hex(32)
                logger.warning(
                    "未配置 AUTH_COOKIE_SECRET，已使用进程级随机密钥；服务重启后现有登录状态将失效"
                )
        return _auth_cookie_secret

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

    def get(self, key: str, default: Any = None) -> Any:
        return _settings.get(key, default)


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
