from asu.build import build
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
    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89",
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
        packages={"test1", "test2"},
    )
    result = build(request_data)
    assert result["id"] == "testprofile"


def test_build_fake_diff_packages(app, upstream):
    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89",
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
        packages={"test1", "test2"},
        diff_packages=True,
    )
    result = build(request_data)
    assert result["id"] == "testprofile"


def test_build_fake_no_packages(app, upstream):
    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89",
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
    )
    result = build(request_data)
    assert result["id"] == "testprofile"


def test_build_fake_list_packages(app, upstream):
    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89",
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
        packages=["test1"],
    )
    with pytest.raises(Exception) as execinfo:
        result = build(request_data)
    assert str(execinfo.value) == "packages must be type set not list"


def test_build_fake_store_path_not_exists(app, upstream):
    app.config["STORE_PATH"].rmdir()

    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89",
        },
        target="testtarget/testsubtarget",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="http://localhost:8001",
        version="SNAPSHOT",
        profile="testprofile",
    )
    with pytest.raises(Exception) as execinfo:
        result = build(request_data)
    assert str(execinfo.value) == "store_path must be existing directory"


@pytest.mark.slow
def test_build_real(app, httpserver: HTTPServer):
    request_data = dict(
        version_data={
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
        },
        target="ath79/generic",
        store_path=app.config["STORE_PATH"],
        cache_path=app.config["CACHE_PATH"],
        upstream_url="https://downloads.cdn.openwrt.org",
        version="SNAPSHOT",
        profile="tplink_tl-wdr4300-v1",
        packages={"tmux", "vim"},
    )
    result = build(request_data)
    assert result["id"] == "tplink_tl-wdr4300-v1"
