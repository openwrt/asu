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
            "enabled": True,
            "path_packages": "DEPRECATED",
            "package_changes": [
                {"source": "auc", "target": "owut", "revision": 26792},
                {
                    "source": "libustream-wolfssl",
                    "target": "libustream-mbedtls",
                    "revision": 21994,
                },
                {"source": "px5g-wolfssl", "target": "px5g-mbedtls", "revision": 21994},
                {
                    "source": "wpad-basic-wolfssl",
                    "target": "wpad-basic-mbedtls",
                    "revision": 21994,
                },
                {
                    "source": "libustream-wolfssl",
                    "target": "libustream-mbedtls",
                    "revision": 21994,
                },
                {"source": "kmod-nft-nat6", "revision": 20282, "mandatory": True},
                {"source": "firewall", "target": "firewall4", "revision": 18611},
            ],
        },
        "23.05": {
            "path": "releases/{version}",
            "enabled": True,
            "path_packages": "DEPRECATED",
            "branch_off_rev": 23069,
            "package_changes": [
                {
                    "source": "libustream-wolfssl",
                    "target": "libustream-mbedtls",
                    "revision": 21994,
                },
                {"source": "px5g-wolfssl", "target": "px5g-mbedtls", "revision": 21994},
                {
                    "source": "wpad-basic-wolfssl",
                    "target": "wpad-basic-mbedtls",
                    "revision": 21994,
                },
                {
                    "source": "libustream-wolfssl",
                    "target": "libustream-mbedtls",
                    "revision": 21994,
                },
                {"source": "kmod-nft-nat6", "revision": 19160, "mandatory": True},
                {"source": "firewall", "target": "firewall4", "revision": 18611},
            ],
        },
        "22.03": {
            "path": "releases/{version}",
            "enabled": True,
            "path_packages": "DEPRECATED",
            "branch_off_rev": 19160,
            "package_changes": [
                {"source": "kmod-nft-nat6", "revision": 19160, "mandatory": True},
                {"source": "firewall", "target": "firewall4", "revision": 18611},
            ],
        },
    }
    server_stats: str = "/stats"
    log_level: str = "INFO"


settings = Settings()
