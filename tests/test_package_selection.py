"""Tests for the package_selection module."""

from asu.build_request import BuildRequest
from asu.package_selection import get_package_list, select_packages


def test_get_package_list_from_packages():
    """Test getting package list from packages field."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=["vim", "tmux", "htop"],
    )
    packages = get_package_list(build_request)
    assert packages == ["vim", "tmux", "htop"]


def test_get_package_list_from_packages_versions():
    """Test getting package list from packages_versions field."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages_versions={"vim": "1.0", "tmux": "2.0"},
    )
    packages = get_package_list(build_request)
    assert "vim" in packages
    assert "tmux" in packages


def test_get_package_list_packages_versions_priority():
    """Test that packages_versions takes priority over packages."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=["old1", "old2"],
        packages_versions={"new1": "1.0", "new2": "2.0"},
    )
    packages = get_package_list(build_request)
    # packages_versions should take priority
    assert "new1" in packages
    assert "new2" in packages


def test_select_packages_no_diff():
    """Test package selection without diff_packages."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=["vim", "tmux"],
        diff_packages=False,
    )
    default_packages = {"base-files", "busybox"}
    profile_packages = {"kmod-test"}
    
    result = select_packages(build_request, default_packages, profile_packages)
    
    # Without diff_packages, should return the original package list
    assert "vim" in result
    assert "tmux" in result


def test_select_packages_with_diff():
    """Test package selection with diff_packages."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=["vim", "tmux", "base-files"],
        diff_packages=True,
    )
    default_packages = {"base-files", "busybox"}
    profile_packages = {"kmod-test"}
    
    result = select_packages(build_request, default_packages, profile_packages)
    
    # With diff_packages, should remove default packages and add negated ones
    assert "vim" in result
    assert "tmux" in result
    # base-files is in default, so it should not be in the result
    # Instead, packages not in the request but in defaults should be negated
    assert "-busybox" in result
    assert "-kmod-test" in result


def test_select_packages_applies_changes():
    """Test that package selection applies version-specific changes."""
    build_request = BuildRequest(
        version="23.05",
        target="mediatek/mt7622",
        profile="foobar",
        packages=["vim"],
        diff_packages=False,
    )
    default_packages = set()
    profile_packages = set()
    
    result = select_packages(build_request, default_packages, profile_packages)
    
    # Should have added kmod-mt7622-firmware due to package_changes
    assert "kmod-mt7622-firmware" in result
    assert "vim" in result


def test_select_packages_empty_packages():
    """Test package selection with empty package list."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=[],
        diff_packages=False,
    )
    default_packages = {"base-files"}
    profile_packages = {"kmod-test"}
    
    result = select_packages(build_request, default_packages, profile_packages)
    
    assert result == []


def test_select_packages_diff_with_empty():
    """Test package selection with diff_packages and empty package list."""
    build_request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        packages=[],
        diff_packages=True,
    )
    default_packages = {"base-files", "busybox"}
    profile_packages = {"kmod-test"}
    
    result = select_packages(build_request, default_packages, profile_packages)
    
    # With diff_packages and empty list, should negate all default packages
    assert "-base-files" in result
    assert "-busybox" in result
    assert "-kmod-test" in result
