from asu.asu import create_app
from pathlib import PosixPath


def test_pathlib(app):
    assert isinstance(app.config["STORE_PATH"], PosixPath)
    assert isinstance(app.config["JSON_PATH"], PosixPath)
    assert app.config["STORE_PATH"].is_dir()
    assert app.config["JSON_PATH"].is_dir()


def test_other(app):
    assert app.config["UPSTREAM_URL"] == "http://localhost:8001"


def test_json_path_latest(client):
    response = client.get("/json/latest.json")
    assert "19.07.7" in response.json["latest"]
    assert "21.02.0" in response.json["latest"]
    assert "SNAPSHOT" in response.json["latest"]
    assert response.status == "200 OK"


def test_json_path_branches(client):
    response = client.get("/json/branches.json")
    assert "19.07" == response.json[2]["name"]
    assert "SNAPSHOT" == response.json[0]["name"]
    assert response.status == "200 OK"


def test_json_store(client):
    response = client.get("/store/")
    assert response.status == "404 NOT FOUND"
