from asu.build import build
from asu.build import StorePathMissingError
from pathlib import Path

import pytest

from pytest_httpserver import HTTPServer


@pytest.fixture
def upstream(httpserver):
    base_url = "/snapshots/targets/testtarget/testsubtarget"
    upstream_path = Path("./tests/upstream/snapshots/targets/testtarget/testsubtarget/")
    expected_file_requests = [
        "sha256sums.sig",
        "sha256sums",
        "openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64.tar.xz",
    ]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes(),
            headers={"Last-Modified": "Thu, 19 Mar 2020 20:27:41 GMT"},
        )


def test_build_fake(app, upstream):
    req = dict(
        branch_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSr8lOdNWjmjpLR+x5/e2O2qahzP9lYyCfg0Eu66iFCuEsuZfj18MiI",
            "versions": ["snapshot"],
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
        packages={"test1", "test2"},
        request_hash="foobar123",
    )
    result = build(req)
    assert result["id"] == "testprofile"


def test_build_fake_diff_packages(app, upstream):
    req = dict(
        branch_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSr8lOdNWjmjpLR+x5/e2O2qahzP9lYyCfg0Eu66iFCuEsuZfj18MiI",
            "versions": ["snapshot"],
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
        packages={"test1", "test2"},
        diff_packages=True,
        request_hash="foobar123",
    )
    result = build(req)
    assert result["id"] == "testprofile"


def test_build_fake_store_path_not_exists(app, upstream):
    app.config["STORE_PATH"].rmdir()

    req = dict(
        branch_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSr8lOdNWjmjpLR+x5/e2O2qahzP9lYyCfg0Eu66iFCuEsuZfj18MiI",
            "versions": ["snapshot"],
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
    )
    with pytest.raises(Exception) as execinfo:
        result = build(req)
    assert execinfo.type == StorePathMissingError


@pytest.mark.slow
def test_build_real(app, httpserver: HTTPServer):
    req = dict(
        branch_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
            "versions": ["snapshot"],
        },
        target="ath79/generic",
        store_path=app.config["STORE_PATH"],
        upstream_url="https://downloads.openwrt.org",
        version="SNAPSHOT",
        profile="tplink_tl-wdr4300-v1",
        packages={"tmux", "vim"},
        request_hash="foobar123",
    )
    result = build(req)
    assert result["id"] == "tplink_tl-wdr4300-v1"
