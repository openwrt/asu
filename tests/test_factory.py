from asu import create_app
from pathlib import PosixPath


def test_config():
    assert not create_app().testing
    assert create_app({"TESTING": True}).testing
    assert type(create_app().config["STORE_PATH"]) == PosixPath


def test_root(client):
    response = client.get("/")
    assert response.status == "200 OK"
