import shutil
import tempfile

import pytest
from fakeredis import FakeStrictRedis

from asu.asu import create_app


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


def redis_load_mock_data(redis):
    redis.sadd(
        "packages-SNAPSHOT-SNAPSHOT-testtarget/testsubtarget", "test1", "test2", "test3"
    )
    redis.sadd("profiles-SNAPSHOT-SNAPSHOT-testtarget/testsubtarget", "testprofile")
    redis.hset(
        "mapping-SNAPSHOT-SNAPSHOT-testtarget/testsubtarget",
        mapping={"testvendor,testprofile": "testprofile"},
    )
    redis.sadd("targets-SNAPSHOT", "testtarget/testsubtarget", "x86/64")
    redis.sadd("targets-21.02", "testtarget/testsubtarget")
    redis.hset("mapping-abi", mapping={"test1-1": "test1"})
    redis.zadd(
        f"stats-profiles-SNAPSHOT",
        {
            "linksys_e8450-ubi": 543,
            "rpi-4": 63,
            "tplink_archer-c60-v1": 39,
            "generic": 38,
            "xiaomi_mi-router-4a-gigabit": 35,
        },
    )

    redis.zadd(
        f"stats-profiles-21.02",
        {
            "xiaomi_mi-router-4a-gigabit": 71,
            "generic": 62,
            "rpi-4": 59,
            "linksys_wrt1900acs": 39,
            "xiaomi_mi-router-3g": 38,
        },
    )

    redis.zadd(
        f"stats-profiles-19.07",
        {
            "archer_c7_v2": 22,
            "generic": 14,
            "rpi-4": 47,
            "linksys_wrt1900acs": 62,
            "xiaomi_mi-router-3g": 65,
        },
    )

    redis.zadd(
        "stats-versions",
        {"SNAPSHOT": 1257, "21.02.0": 755, "19.07.8": 115},
    )

    redis.set("stats-images", 1245)
    redis.set("stats-images-custom", 200)


def mock_app(test_path="."):
    redis = FakeStrictRedis()
    redis_load_mock_data(redis)
    app = create_app(
        {
            "JSON_PATH": test_path + "/json",
            "REDIS_CONN": redis,
            "STORE_PATH": test_path + "/store",
            "TESTING": True,
            "UPSTREAM_URL": "http://localhost:8001",
            "BRANCHES": {
                "SNAPSHOT": {
                    "name": "SNAPSHOT",
                    "enabled": True,
                    "snapshot": True,
                    "versions": ["SNAPSHOT"],
                    "git_branch": "master",
                    "path": "snapshots",
                    "path_packages": "snapshots/packages",
                    "repos": ["base"],
                    "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
                    "updates": "dev",
                    "targets": {
                        "testtarget/testsubtarget": "testarch",
                        "x86/64": "x86_64",
                    },
                },
                "21.02": {
                    "name": "21.02",
                    "enabled": True,
                    "snapshot": True,
                    "versions": ["21.02.0", "21.02.0-rc4", "21.02-SNAPSHOT"],
                    "git_branch": "openwrt-21.02",
                    "path": "releases/{version}",
                    "path_packages": "releases/packages-{branch}",
                    "repos": ["base"],
                    "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
                    "updates": "rc",
                    "targets": {"testtarget/testsubtarget": "testarch"},
                },
                "19.07": {
                    "name": "19.07",
                    "enabled": True,
                    "versions": ["19.07.7", "19.07.6"],
                    "git_branch": "openwrt-19.07",
                    "path": "releases/{version}",
                    "path_packages": "releases/packages-{branch}",
                    "repos": ["base"],
                    "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
                    "updates": "stable",
                    "targets": {"testtarget/testsubtarget": "testarch"},
                },
            },
        }
    )

    return app


@pytest.fixture
def app():
    test_path = tempfile.mkdtemp()
    yield mock_app(test_path)
    shutil.rmtree(test_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8001)
