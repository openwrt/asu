import pytest
import tempfile
import shutil

from fakeredis import FakeStrictRedis

from asu import create_app


@pytest.fixture
def app():
    store_path = tempfile.mkdtemp()
    app = create_app(
        {
            "TESTING": True,
            "STORE_PATH": store_path,
            "JSON_PATH": "./tests/json/",
            "REDIS_CONN": FakeStrictRedis(),
        }
    )

    yield app

    shutil.rmtree(store_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
