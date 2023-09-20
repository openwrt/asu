from pathlib import Path

import pytest

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
    # with app.app_context():
    update_branch(
        {**app.config, "JSON_PATH": app.config["PUBLIC_PATH"] / "json/v1"},
        app.config["BRANCHES"]["SNAPSHOT"],
    )
    assert (app.config["PUBLIC_PATH"] / "json/v1/snapshots/overview.json").is_file()


def test_update_meta_latest_json(app):
    with app.app_context():
        update_meta_json(
            {**app.config, "JSON_PATH": app.config["PUBLIC_PATH"] / "json/v1"}
        )
    latest_json = json.loads(
        (app.config["PUBLIC_PATH"] / "json/v1/latest.json").read_text()
    )
    assert "19.07.7" in latest_json["latest"]
    assert "21.02.7" in latest_json["latest"]
    assert "SNAPSHOT" in latest_json["latest"]


def test_update_meta_overview_json(app):
    with app.app_context():
        update_meta_json(
            {**app.config, "JSON_PATH": app.config["PUBLIC_PATH"] / "json/v1"}
        )
    overview_json = json.loads(
        (app.config["PUBLIC_PATH"] / "json/v1/overview.json").read_text()
    )
    assert "package_changes" in overview_json["branches"]["1.2"]
