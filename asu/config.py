from pathlib import Path
from typing import Union

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    public_path: Path = Path.cwd() / "public"
    json_path: Path = public_path / "json" / "v1"
    redis_url: str = "redis://localhost:6379"
    upstream_url: str = "https://downloads.openwrt.org"
    allow_defaults: bool = False
    async_queue: bool = True
    branches_file: Union[str, Path, None] = None
    max_custom_rootfs_size_mb: int = 1024
    repository_allow_list: list = []
    base_container: str = "ghcr.io/openwrt/imagebuilder"
    update_token: Union[str, None] = "foobar"
    container_host: str = "localhost"
    container_identity: str = ""
    branches: dict = {
        "SNAPSHOT": {
            "path": "snapshots",
        },
        "default": {"path": "releases/{version}"},
    }
    server_stats: str = "/stats"
    log_level: str = "INFO"


settings = Settings()
