from pathlib import PosixPath


def test_pathlib(app):
    assert isinstance(app.config["STORE_PATH"], PosixPath)
    assert isinstance(app.config["JSON_PATH"], PosixPath)
    assert app.config["STORE_PATH"].is_dir()
    assert app.config["JSON_PATH"].is_dir()


def test_branches_yaml(app_using_branches_yml):
    assert isinstance(app_using_branches_yml.config["BRANCHES"], dict)
    assert "SNAPSHOT" in app_using_branches_yml.config["BRANCHES"]
    assert "22.03" in app_using_branches_yml.config["BRANCHES"]


def test_branches_default(app_using_default_branches):
    assert isinstance(app_using_default_branches.config["BRANCHES"], dict)
    assert "SNAPSHOT" in app_using_default_branches.config["BRANCHES"]
    assert "22.03" in app_using_default_branches.config["BRANCHES"]


def test_other(app):
    assert app.config["UPSTREAM_URL"] == "http://localhost:8001"


def test_json_store(client):
    response = client.get("/store/")
    assert response.status == "404 NOT FOUND"
