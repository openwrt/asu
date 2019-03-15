import json

from asu.utils.config import Config


def test_config_init():
    assert Config()


def test_config_version():
    assert Config().version("openwrt", "18.06.0") is not None


def test_config_distro_alias():
    assert Config().config["distros"]["openwrt"]["distro_alias"] == "OpenWrt"


def test_config_version_distro_vanilla():
    assert Config().version("openwrt", "18.06.0")["vanilla"] == ["luci"]


def test_config_get_all():
    assert json.loads(Config().get_all())["openwrt"]["distro_alias"] == "OpenWrt"
