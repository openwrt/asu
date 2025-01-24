from pathlib import Path
from typing import Union

from pydantic_settings import BaseSettings, SettingsConfigDict

package_changes_list = [
    {"source": "firewall", "target": "firewall4", "revision": 18611},
    {"source": "kmod-nft-nat6", "revision": 20282, "mandatory": True},
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
    {"source": "auc", "target": "owut", "revision": 26792},
    {
        "source": "luci-app-opkg",
        "target": "luci-app-package-manager",
        "revision": 27897,
    },
    {"source": "opkg", "target": "apk-mbedtls", "revision": 28056},
]


def package_changes(before=None):
    changes = []
    for change in package_changes_list:
        if before is None or change["revision"] <= before:
            changes.append(change)
    return changes


def release(branch_off_rev, enabled=True):
    return {
        "path": "releases/{version}",
        "enabled": enabled,
        "path_packages": "DEPRECATED",
        "branch_off_rev": branch_off_rev,
        "package_changes": package_changes(branch_off_rev),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    public_path: Path = Path.cwd() / "public"

    @property
    def json_path(self):
        return self.public_path / "json" / "v1"
    
    redis_url: str = "redis://localhost:6379"
    upstream_url: str = "https://downloads.openwrt.org"
    allow_defaults: bool = False
    async_queue: bool = True
    branches_file: Union[str, Path, None] = None
    max_custom_rootfs_size_mb: int = 1024
    max_defaults_length: int = 20480
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
            "package_changes": package_changes(),
        },
        "24.10": release(27990),
        "23.05": release(23069),
        "22.03": release(19160),
        "21.02": release(15812, enabled=True),  # Enabled for now...
    }
    server_stats: str = "/stats"
    log_level: str = "INFO"
    squid_cache: bool = False


settings = Settings()
