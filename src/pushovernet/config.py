import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pushovernet.exceptions import PushoverConfigError

DEFAULT_CONFIG_PATH = Path("~/.config/pushovernet/config.toml").expanduser()


@dataclass
class PushoverConfig:
    token: str
    user_key: str
    default_device: str = ""
    default_priority: int = 0
    default_sound: str = ""

    @classmethod
    def from_toml(cls, path: Path | str | None = None) -> "PushoverConfig":
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not path.exists():
            raise PushoverConfigError(f"Config file not found: {path}")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        section = data.get("pushover")
        if not section:
            raise PushoverConfigError(f"Missing [pushover] section in {path}")
        try:
            return cls(
                token=section["token"],
                user_key=section["user_key"],
                default_device=section.get("default_device", ""),
                default_priority=section.get("default_priority", 0),
                default_sound=section.get("default_sound", ""),
            )
        except KeyError as e:
            raise PushoverConfigError(f"Missing required config key: {e}") from e

    @classmethod
    def from_aws_secret(cls, secret_name: str, region: str = "us-east-1") -> "PushoverConfig":
        from pushovernet._aws import get_secret

        secret = get_secret(secret_name, region)
        try:
            return cls(
                token=secret["token"],
                user_key=secret["user_key"],
                default_device=secret.get("default_device", ""),
                default_priority=secret.get("default_priority", 0),
                default_sound=secret.get("default_sound", ""),
            )
        except KeyError as e:
            raise PushoverConfigError(f"Missing required secret key: {e}") from e

    @classmethod
    def from_env(cls) -> "PushoverConfig":
        token = os.environ.get("PUSHOVER_TOKEN")
        user_key = os.environ.get("PUSHOVER_USER_KEY")
        if not token or not user_key:
            raise PushoverConfigError(
                "PUSHOVER_TOKEN and PUSHOVER_USER_KEY environment variables are required"
            )
        return cls(token=token, user_key=user_key)


@dataclass
class ServerConfig:
    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 9505

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ServerConfig":
        host = os.environ.get("PUSHOVERNET_HOST")
        port = os.environ.get("PUSHOVERNET_PORT")
        api_key = os.environ.get("PUSHOVERNET_API_KEY")

        path = Path(path) if path else DEFAULT_CONFIG_PATH
        section: dict = {}
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            section = data.get("server", {})

        return cls(
            api_key=api_key or section.get("api_key", ""),
            host=host or section.get("host", "0.0.0.0"),
            port=int(port) if port else section.get("port", 9505),
        )


@dataclass
class ProxyConfig:
    url: str = "http://localhost:9505"
    api_key: str = ""

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ProxyConfig":
        url = os.environ.get("PUSHOVERNET_PROXY_URL")
        api_key = os.environ.get("PUSHOVERNET_PROXY_API_KEY")

        path = Path(path) if path else DEFAULT_CONFIG_PATH
        section: dict = {}
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            section = data.get("proxy", {})

        return cls(
            url=url or section.get("url", "http://localhost:9505"),
            api_key=api_key or section.get("api_key", ""),
        )
