from asu.repositories import (
    is_apk_build,
    merge_apk_repositories,
    merge_repositories_conf,
    normalize_apk_repo_url,
    render_apk_repositories,
    render_repositories_conf,
)


def test_merge_repositories_conf_replaces_src_gz_entries():
    base = (
        "src/gz foo https://example.com/old\n"
        "src/gz bar https://example.com/bar\n"
        "option check_signature\n"
        "src imagebuilder file:packages\n"
    )

    merged = merge_repositories_conf(
        base,
        {
            "foo": "https://example.com/new",
            "baz": "https://example.com/baz",
        },
    )

    assert "src/gz foo https://example.com/new" in merged
    assert "src/gz foo https://example.com/old" not in merged
    assert "src/gz bar https://example.com/bar" in merged
    assert "src/gz baz https://example.com/baz" in merged


def test_merge_repositories_conf_adds_required_imagebuilder_lines_if_missing():
    base = "src/gz foo https://example.com/old\n"

    merged = merge_repositories_conf(base, {"bar": "https://example.com/bar"})

    assert "src imagebuilder file:packages" in merged
    assert "option check_signature" in merged


def test_is_apk_build_version_threshold():
    assert not is_apk_build("24.10.0")
    assert is_apk_build("25.12.0")
    assert is_apk_build("25.12.1-rc1")
    assert is_apk_build("26.1.0")


def test_normalize_apk_repo_url_adds_packages_adb_suffix():
    assert (
        normalize_apk_repo_url("https://example.com/releases/23.05")
        == "https://example.com/releases/23.05/packages.adb"
    )
    assert (
        normalize_apk_repo_url("https://example.com/rep/packages.adb")
        == "https://example.com/rep/packages.adb"
    )


def test_merge_apk_repositories_appends_normalized_urls_only():
    base = "https://example.com/a/packages.adb\nhttps://example.com/b/packages.adb\n"
    merged = merge_apk_repositories(
        base,
        [
            "https://example.com/b",  # should normalize and dedupe
            "https://example.com/c/packages.adb",  # already normalized
            "https://example.com/d/",  # should normalize
        ],
    )

    assert "https://example.com/a/packages.adb" in merged
    assert "https://example.com/b/packages.adb" in merged
    assert "https://example.com/c/packages.adb" in merged
    assert "https://example.com/d/packages.adb" in merged
    assert merged.count("https://example.com/b/packages.adb\n") == 1


def test_render_repositories_conf_replace_mode_drops_base_repositories():
    base = (
        "src/gz foo https://example.com/old\n"
        "src/gz bar https://example.com/bar\n"
        "option check_signature\n"
        "src imagebuilder file:packages\n"
    )

    rendered = render_repositories_conf(
        base,
        {"foo": "https://example.com/new", "baz": "https://example.com/baz"},
        "replace",
    )

    assert "src/gz foo https://example.com/new" in rendered
    assert "src/gz baz https://example.com/baz" in rendered
    assert "src/gz bar https://example.com/bar" not in rendered
    assert "option check_signature" in rendered
    assert "src imagebuilder file:packages" in rendered


def test_render_repositories_conf_replace_mode_with_empty_extra_is_minimal():
    base = "src/gz bar https://example.com/bar\n"
    rendered = render_repositories_conf(base, {}, "replace")
    assert "src/gz bar https://example.com/bar" not in rendered
    assert "option check_signature" in rendered
    assert "src imagebuilder file:packages" in rendered


def test_render_apk_repositories_replace_mode_uses_only_extra():
    base = "https://example.com/a/packages.adb\nhttps://example.com/b/packages.adb\n"
    rendered = render_apk_repositories(
        base,
        [
            "https://example.com/b",
            "https://example.com/c/packages.adb",
        ],
        "replace",
    )
    assert "https://example.com/a/packages.adb" not in rendered
    assert "https://example.com/b/packages.adb" in rendered
    assert "https://example.com/c/packages.adb" in rendered


def test_render_apk_repositories_replace_mode_empty_extra_is_empty_file():
    base = "https://example.com/a/packages.adb\n"
    rendered = render_apk_repositories(base, [], "replace")
    assert rendered == "\n"
