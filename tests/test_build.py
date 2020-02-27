from asu.build import build
from pathlib import Path

import pytest

from pytest_httpserver import HTTPServer


def test_build_fake(app, httpserver: HTTPServer):
    base_url = "/snapshots/targets/testtarget/testsubtarget"
    upstream_path = Path("./tests/upstream/snapshots/targets/testtarget/testsubtarget/")
    expected_file_requests = [
        "sha256sums.sig",
        "sha256sums",
        "openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64.tar.xz",
    ]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes()
        )

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
        packages=["test1", "test2"],
    )
    result = build(request_data)
    assert result["id"] == "testprofile"


@pytest.mark.skip(reason="upstream package iw is currently broken")
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
        upstream_url="https://cdn.openwrt.org",
        version="SNAPSHOT",
        profile="8devices_carambola",
        packages=["tmux", "vim"],
    )
    result = build(request_data)
    assert result["id"] == "8devices_carambola"
