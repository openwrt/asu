import shutil
import tempfile
from pathlib import Path

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient

from asu.config import settings
from asu.main import app as real_app


def redis_load_mock_data(redis):
    redis.sadd(
        "packages:1.2:1.2.3:testtarget/testsubtarget",
        "test1",
        "test2",
        "test3",
        "valid_new_package",
    )
    redis.sadd("profiles:1.2:1.2.3:testtarget/testsubtarget", "testprofile")
    redis.sadd("profiles:SNAPSHOT:SNAPSHOT:ath79/generic", "tplink_tl-wdr4300-v1")
    redis.sadd("packages:SNAPSHOT:SNAPSHOT:ath79/generic", "vim", "tmux")
    redis.sadd("packages:SNAPSHOT:SNAPSHOT:x86/64", "vim", "tmux")

    redis.sadd("branches", "SNAPSHOT", "1.2", "21.02", "19.07")
    redis.sadd("versions:SNAPSHOT", "SNAPSHOT")
    redis.sadd("versions:1.2", "1.2.3")
    redis.sadd("versions:21.02", "21.02.7", "21.02.0", "21.02.0-rc4", "21.02-SNAPSHOT")
    redis.sadd("versions:19.07", "19.07.7", "19.07.6")

    redis.sadd("profiles:21.02:21.02.7:ath79/generic", "tplink_tl-wdr4300-v1")
    redis.sadd("packages:21.02:21.02.7:ath79/generic", "vim", "tmux")
    redis.sadd("packages:21.02:21.02.7:x86/64", "vim", "tmux")

    redis.sadd("profiles:21.02:21.02.7:x86/64", "generic")
    redis.set("revision:21.02.7:x86/64", "r16847-f8282da11e")

    redis.hset(
        "mapping:1.2:1.2.3:testtarget/testsubtarget",
        mapping={"testvendor,testprofile": "testprofile"},
    )
    redis.hset("targets:1.2", mapping={"testtarget/testsubtarget": "testarch"})
    redis.hset("targets:SNAPSHOT", mapping={"ath79/generic": "", "x86/64": ""})
    redis.hset(
        "targets:21.02",
        mapping={
            "testtarget/testsubtarget": "testarch",
            "ath79/generic": "",
            "x86/64": "",
        },
    )
    redis.hset("mapping-abi", mapping={"test1-1": "test1"})


@pytest.fixture
def redis_server():
    r = FakeStrictRedis()
    redis_load_mock_data(r)
    yield r
    r.flushall()


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture
def test_path():
    test_path = tempfile.mkdtemp(dir=Path.cwd() / "tests")
    yield test_path
    shutil.rmtree(test_path)


@pytest.fixture
def app(redis_server, test_path, monkeypatch):
    def mocked_redis_client(*args, **kwargs):
        return redis_server

    settings.public_path = Path(test_path) / "public"
    settings.async_queue = False
    for branch in "1.2", "19.07", "21.02":
        if branch not in settings.branches:
            settings.branches[branch] = {"path": "releases/{version}"}

    monkeypatch.setattr("asu.util.get_redis_client", mocked_redis_client)
    monkeypatch.setattr("asu.routers.api.get_redis_client", mocked_redis_client)

    yield real_app


@pytest.fixture
def client(app):
    yield TestClient(app)


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8001)
