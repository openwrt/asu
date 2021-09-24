from asu.build import build
from pathlib import Path

import pytest

from pytest_httpserver import HTTPServer

from asu.janitor import *


@pytest.fixture
def upstream(httpserver):
    base_url = "/snapshots"
    upstream_path = Path("./tests/upstream/snapshots/")
    expected_file_requests = [
        "packages/testarch/base/Packages.manifest",
        "targets/testtarget/testsubtarget/packages/Packages.manifest",
        "targets/testtarget/testsubtarget/profiles.json",
    ]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes()
        )

    httpserver.expect_request(
        f"{base_url}/targets", query_string="json-targets"
    ).respond_with_json(["testtarget/testsubtarget"])


def test_update_branch(app, upstream):
    with app.app_context():
        update_branch(app.config["BRANCHES"]["SNAPSHOT"])
    assert (app.config["JSON_PATH"] / "snapshots/overview.json").is_file()


def test_parse_packages_file(app, upstream):
    url = (
        app.config["UPSTREAM_URL"]
        + "/snapshots/packages/testarch/base/Packages.manifest"
    )
    with app.app_context():
        packages = parse_packages_file(url, "base")
    assert "6rd" in packages.keys()


def test_parse_packages_file_bad(app, upstream):
    url = app.config["UPSTREAM_URL"] + "/snapshots/packages/testarch/base/NoPackages"
    with app.app_context():
        packages = parse_packages_file(url, "base")


def test_get_packages_target_base(app, upstream):
    branch = app.config["BRANCHES"]["SNAPSHOT"]
    version = "snapshots"
    target = "testtarget/testsubtarget"
    with app.app_context():
        packages = get_packages_target_base(branch, version, target)
    assert "base-files" in packages.keys()


def test_update_target_packages(app, upstream):
    branch = app.config["BRANCHES"]["SNAPSHOT"]
    version = "snapshots"
    target = "testtarget/testsubtarget"
    with app.app_context():
        packages = update_target_packages(branch, version, target)
    assert (
        app.config["JSON_PATH"]
        / "snapshots/targets/testtarget/testsubtarget/index.json"
    ).is_file()


def test_update_arch_packages(app, upstream):
    branch = app.config["BRANCHES"]["SNAPSHOT"]
    arch = "testarch"
    with app.app_context():
        packages = update_arch_packages(branch, arch)
    assert (
        app.config["JSON_PATH"] / "snapshots/packages/testarch-index.json"
    ).is_file()
