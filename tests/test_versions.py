import runpy
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from asu.config import settings
from asu.routers.api import validate_request
from asu.build_request import BuildRequest
from asu.util import reload_versions


@pytest.fixture
def version_data():
    return {
        "upcoming_version": "",
        "stable_version": "1.2.3",
        "oldstable_version": "",
        "versions_list": ["1.2.3"],
    }


@pytest.fixture
def load_app(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "public_path", tmp_path)
    monkeypatch.setattr(
        settings,
        "branches",
        {"1.2": {"path": "releases/{version}", "enabled": True}},
    )
    get = Mock()
    monkeypatch.setattr("asu.util.client_get", get)

    def load(result):
        if isinstance(result, Exception):
            get.side_effect = result
        else:
            get.return_value = result
        namespace = runpy.run_path("asu/main.py")
        return namespace["app"], get

    return load


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("Connection failed"),
        httpx.ReadTimeout("Timed out"),
        httpx.Response(503),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={}),
        httpx.Response(200, json=None),
        httpx.Response(200, json=[]),
    ],
)
def test_startup_version_failure(load_app, version_data, failure):
    app, get = load_app(failure)
    assert app.versions == []
    assert app.latest == []

    with TestClient(app) as client:
        assert client.get("/json/v1/latest.json").status_code == 503
        get.side_effect = None
        get.return_value = httpx.Response(200, json=version_data)
        response = client.get("/json/v1/latest.json")
        assert response.status_code == 200
        assert response.json() == {"latest": ["1.2.3"]}
        assert app.versions == ["1.2.3", "1.2-SNAPSHOT"]


@pytest.mark.parametrize(
    "path", ["/", "/json/v1/branches.json", "/json/v1/overview.json"]
)
def test_version_endpoints_retry(load_app, version_data, path):
    app, get = load_app(httpx.ConnectError("Connection failed"))
    with TestClient(app) as client:
        assert client.get(path).status_code == 503

        def recovered_get(url):
            return httpx.Response(
                200, json=version_data if url.endswith("/.versions.json") else {}
            )

        get.side_effect = recovered_get
        assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("Timed out"),
        httpx.Response(502),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"upcoming_version": "1.2.4"}),
    ],
)
def test_version_refresh_keeps_previous_data(load_app, version_data, failure):
    app, get = load_app(httpx.Response(200, json=version_data))
    versions, latest = list(app.versions), list(app.latest)
    if isinstance(failure, Exception):
        get.side_effect = failure
    else:
        get.return_value = failure

    assert reload_versions(app) is False
    assert app.versions == versions
    assert app.latest == latest
    with TestClient(app) as client:
        response = client.get("/json/v1/latest.json")
        assert response.status_code == 200
        assert response.json() == {"latest": latest}


@pytest.mark.parametrize(
    "field,value",
    [
        ("upcoming_version", 123),
        ("stable_version", {}),
        ("oldstable_version", []),
        ("versions_list", "1.2.3"),
        ("versions_list", None),
        ("versions_list", ["1.2.4", 123]),
    ],
)
def test_invalid_version_fields_keep_previous_data(
    load_app, version_data, field, value
):
    app, get = load_app(httpx.Response(200, json=version_data))
    versions, latest = list(app.versions), list(app.latest)
    get.return_value = httpx.Response(200, json={**version_data, field: value})
    assert reload_versions(app) is False
    assert app.versions == versions
    assert app.latest == latest


def test_build_without_version_information(load_app):
    app, get = load_app(httpx.ConnectError("Connection failed"))
    request = BuildRequest(version="1.2.3", target="test/target", profile="test")
    content, status = validate_request(app, request)
    assert status == 503
    assert content["detail"] == "Version information unavailable"
    assert get.call_count == 2
