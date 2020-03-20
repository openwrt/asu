from asu.build import build
from pathlib import Path
import redis

import pytest

from pytest_httpserver import HTTPServer

from asu.janitor import *


def test_get_packages_arch(app, httpserver: HTTPServer, redis):
    base_url = "/snapshots/packages/x86_64/base"
    upstream_path = Path("./tests/upstream/snapshots/packages/x86_64/base")
    expected_file_requests = ["Packages"]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes()
        )

    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        get_packages_arch(version, sources=["base"])
    assert b"base-files" in redis.smembers("packages-snapshot")


def test_get_packages_target(app, httpserver: HTTPServer, redis):
    base_url = "/snapshots/targets/testtarget/testsubtarget/packages"
    upstream_path = Path(
        "./tests/upstream/snapshots/targets/testtarget/testsubtarget/packages"
    )
    expected_file_requests = ["Packages"]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes()
        )

    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        assert get_packages_target((version, "testtarget/testsubtarget")) == (
            "testtarget/testsubtarget",
            ["base-files", "block-mount", "blockd"],
        )


def test_get_packages_targets(app, httpserver: HTTPServer, redis):
    base_url = "/snapshots/targets/testtarget/testsubtarget/packages"
    upstream_path = Path(
        "./tests/upstream/snapshots/targets/testtarget/testsubtarget/packages"
    )
    expected_file_requests = ["Packages"]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes()
        )

    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        get_packages_targets(version)
    assert redis.smembers("packages-snapshot-testtarget/testsubtarget") == {
        b"base-files",
        b"block-mount",
        b"blockd",
    }


def test_get_json_files(app, httpserver: HTTPServer, redis):
    base_url = "/snapshots/targets"
    upstream_path = Path("./tests/upstream/snapshots/targets")
    expected_file_requests = [""]

    httpserver.expect_request(f"{base_url}/", query_string="json").respond_with_data(
        (upstream_path / "?json").read_bytes()
    )
    httpserver.expect_request(
        f"{base_url}/testtarget/testsubtarget/openwrt-testtarget-testsubtarget-testprofile.json"
    ).respond_with_data(
        (
            upstream_path
            / "testtarget/testsubtarget/openwrt-testtarget-testsubtarget-testprofile.json"
        ).read_bytes()
    )

    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        get_json_files(version)
    assert redis.hgetall("profiles-snapshot") == {
        b"8devices_carambola": b"ramips/rt305x",
        b"testprofile": b"testtarget/testsubtarget",
    }
    assert len(redis.hgetall("profiles-snapshot")) == 2


def test_get_packages_arch_real(app, httpserver: HTTPServer, redis):
    app.config["UPSTREAM_URL"] = "https://cdn.openwrt.org"
    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        get_packages_arch(version, sources=["base", "luci"])
    assert len(redis.smembers("packages-snapshot")) > 2000


@pytest.mark.slow
@pytest.mark.skip
def test_get_json_files_real(app, httpserver: HTTPServer, redis):
    app.config["UPSTREAM_URL"] = "https://cdn.openwrt.org"
    version = app.config["VERSIONS"]["branches"][0]
    with app.app_context():
        get_json_files(version)
    assert len(redis.hgetall("profiles-snapshot")) > 900
