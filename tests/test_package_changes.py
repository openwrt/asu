from asu.package_changes import appy_package_changes


def test_apply_package_changes_adds_kmod_switch_rtl8366s():
    req = {
        "version": "23.05",
        "target": "ath79/generic",
        "profile": "buffalo_wzr-hp-g300nh-s",
        "packages": ["kmod-ath9k-htc"],
    }
    appy_package_changes(req)

    assert "kmod-switch-rtl8366s" in req["packages"]


def test_apply_package_changes_does_not_add_duplicate_packages():
    req = {
        "version": "23.05",
        "target": "ath79/generic",
        "profile": "buffalo_wzr-hp-g300nh-s",
        "packages": ["kmod-ath9k-htc", "kmod-switch-rtl8366s"],
    }
    appy_package_changes(req)

    assert req["packages"] == ["kmod-ath9k-htc", "kmod-switch-rtl8366s"]


def test_apply_package_changes_does_not_modify_input_dict():
    req = {
        "version": "23.05",
        "target": "ath79/generic",
        "profile": "buffalo_wzr-hp-g300nh-s",
        "packages": ["kmod-ath9k-htc"],
    }
    original_req = req.copy()
    appy_package_changes(req)

    assert req == original_req


def test_apply_package_changes_release():
    req = {
        "version": "21.02.0-rc1",
        "target": "ath79/generic",
        "profile": "buffalo_wzr-hp-g300nh-s",
        "packages": ["kmod-ath9k-htc"],
    }
    appy_package_changes(req)

    original_req = req.copy()
    appy_package_changes(req)

    assert req == original_req


def test_apply_package_changes_mediatek():
    req = {
        "version": "23.05",
        "target": "mediatek/mt7622",
        "profile": "foobar",
        "packages": ["ubus"],
    }
    appy_package_changes(req)

    assert "kmod-mt7622-firmware" in req["packages"]
