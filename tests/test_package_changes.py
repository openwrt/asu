from asu.build_request import BuildRequest
from asu.package_changes import appy_package_changes


def test_apply_package_changes_adds_kmod_switch_rtl8366s():
    build_request = BuildRequest(
        **{
            "version": "23.05",
            "target": "ath79/generic",
            "profile": "buffalo_wzr-hp-g300nh-s",
            "packages": ["kmod-ath9k-htc"],
        }
    )
    appy_package_changes(build_request)

    assert "kmod-switch-rtl8366s" in build_request.packages


def test_apply_package_changes_does_not_add_duplicate_packages():
    build_request = BuildRequest(
        **{
            "version": "23.05",
            "target": "ath79/generic",
            "profile": "buffalo_wzr-hp-g300nh-s",
            "packages": ["kmod-ath9k-htc", "kmod-switch-rtl8366s"],
        }
    )
    appy_package_changes(build_request)

    assert build_request.packages == ["kmod-ath9k-htc", "kmod-switch-rtl8366s"]


def test_apply_package_changes_does_not_modify_input_dict():
    build_request = BuildRequest(
        **{
            "version": "23.05",
            "target": "ath79/generic",
            "profile": "buffalo_wzr-hp-g300nh-s",
            "packages": ["kmod-ath9k-htc"],
        }
    )
    original_req = build_request.model_copy()
    appy_package_changes(build_request)

    assert build_request == original_req


def test_apply_package_changes_release():
    build_request = BuildRequest(
        **{
            "version": "21.02.0-rc1",
            "target": "ath79/generic",
            "profile": "buffalo_wzr-hp-g300nh-s",
            "packages": ["kmod-ath9k-htc"],
        }
    )
    appy_package_changes(build_request)

    original_build_request = build_request.model_copy()
    appy_package_changes(build_request)

    assert build_request == original_build_request


def test_apply_package_changes_mediatek():
    build_request = BuildRequest(
        **{
            "version": "23.05",
            "target": "mediatek/mt7622",
            "profile": "foobar",
            "packages": ["ubus"],
        }
    )
    appy_package_changes(build_request)

    assert "kmod-mt7622-firmware" in build_request.packages
