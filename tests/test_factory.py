from asu import create_app
from pathlib import PosixPath


def test_config():
    assert not create_app().testing
    assert create_app({"TESTING": True}).testing
    assert isinstance(create_app().config["STORE_PATH"], PosixPath)
