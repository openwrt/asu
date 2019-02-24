import pytest

from asu.utils.config import Config


def test_config_init():
    assert Config()


def test_config_version():
    assert Config().version("openwrt", "18.06.0") is not None


def test_config_version_distro_alias():
    assert (
        Config().version("openwrt", "18.06.0").get("distro_alias") == "OpenWrt"
    )


def test_config_version_distro_vanilla():
    assert Config().version("openwrt", "18.06.0").get("vanilla") == ["luci"]
