from typing import Annotated, Optional

from pydantic import BaseModel, Field

from asu.config import settings


class BuildRequest(BaseModel):
    distro: str = "openwrt"
    version: str
    version_code: Annotated[
        str,
        Field(
            default="",
            description="It is possible to send the expected revision. "
            "This allows to show the revision within clients before the "
            "request. If the resulting firmware is a different revision, "
            "the build results in an error.",
        ),
    ] = ""
    target: str
    packages: Optional[list[str]] = []
    profile: str
    packages_versions: Optional[dict] = {}
    defaults: Optional[
        Annotated[
            str,
            Field(
                default=None,
                max_length=settings.max_defaults_length,
                description="Custom shell script embedded in firmware image to be run on first\n"
                "boot. This feature might be dropped in the future. Input file size\n"
                f"is limited to {settings.max_defaults_length} bytes and cannot be exceeded.",
            ),
        ]
    ] = None
    client: Optional[str] = None
    rootfs_size_mb: Optional[
        Annotated[
            int,
            Field(
                default=None,
                ge=1,
                le=settings.max_custom_rootfs_size_mb,
                description="Ability to specify a custom CONFIG_TARGET_ROOTFS_PARTSIZE for the\n"
                "resulting image. Attaching this optional parameter will cause\n"
                "ImageBuilder to build a rootfs with that size in MB.",
            ),
        ]
    ] = None
    diff_packages: Optional[bool] = False
    repositories: Optional[dict[str, str]] = {}
    repository_keys: Optional[list[str]] = []
