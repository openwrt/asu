import pytest
import shutil
import tempfile

from fakeredis import FakeStrictRedis

from asu import create_app


@pytest.fixture
def app():
    test_path = tempfile.mkdtemp()
    app = create_app(
        {
            "TESTING": True,
            "STORE_PATH": test_path + "/store",
            "JSON_PATH": "./tests/json/",
            "CACHE_PATH": test_path + "/cache",
            "REDIS_CONN": FakeStrictRedis(),
        }
    )

    yield app

    shutil.rmtree(test_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def httpserver_listen_address():
    return ("127.0.0.1", 8001)
