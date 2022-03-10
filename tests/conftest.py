import shutil
import tempfile
from pathlib import Path

import prometheus_client
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
        "packages-TESTVERSION-TESTVERSION-testtarget/testsubtarget",
        "test1",
        "test2",
        "test3",
    )
    redis.sadd(
        "profiles-TESTVERSION-TESTVERSION-testtarget/testsubtarget", "testprofile"
    )
    redis.sadd("profiles-SNAPSHOT-SNAPSHOT-ath79/generic", "tplink_tl-wdr4300-v1")
    redis.sadd("packages-SNAPSHOT-SNAPSHOT-ath79/generic", "vim", "tmux")
    redis.sadd("packages-SNAPSHOT-SNAPSHOT-x86/64", "vim", "tmux")

    redis.hset(
        "mapping-TESTVERSION-TESTVERSION-testtarget/testsubtarget",
        mapping={"testvendor,testprofile": "testprofile"},
    )
    redis.sadd("targets-TESTVERSION", "testtarget/testsubtarget")
    redis.sadd("targets-SNAPSHOT", "ath79/generic", "x86/64")
    redis.sadd("targets-21.02", "testtarget/testsubtarget")
    redis.hset("mapping-abi", mapping={"test1-1": "test1"})


@pytest.fixture()
def redis_server():
    r = FakeStrictRedis()
    yield r
    r.flushall()


@pytest.fixture
def test_path():
    test_path = tempfile.mkdtemp()
    yield test_path
    shutil.rmtree(test_path)


@pytest.fixture
def app(test_path, redis_server):
    redis_load_mock_data(redis_server)

    registry = prometheus_client.CollectorRegistry(auto_describe=True)

    mock_app = create_app(
        {
            "REGISTRY": registry,
            "ASYNC_QUEUE": False,
            "JSON_PATH": test_path + "/json",
            "REDIS_CONN": redis_server,
            "STORE_PATH": test_path + "/store",
            "TESTING": True,
            "UPSTREAM_URL": "http://localhost:8001",
            "BRANCHES": {
                "SNAPSHOT": {
                    "name": "SNAPSHOT",
                    "updates": "dev",
                    "enabled": True,
                    "snapshot": True,
                    "versions": ["SNAPSHOT"],
                    "git_branch": "master",
                    "path": "snapshots",
                    "path_packages": "snapshots/packages",
                    "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
                    "repos": ["base", "packages", "luci", "routing", "telephony"],
                    "extra_repos": {},
                    "extra_keys": [],
                },
                "TESTVERSION": {
                    "name": "TESTVERSION",
                    "enabled": True,
                    "snapshot": True,
                    "versions": ["TESTVERSION"],
                    "git_branch": "master",
                    "path": "snapshots",
                    "path_packages": "snapshots/packages",
                    "repos": ["base"],
                    "pubkey": "RWRqylWEtrAZQ9hlSSEkqCJD4SAFswJQR1yoMfD3mzO3TEnY7LGthxPi",
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
                    "pubkey": "RWRqylWEtrAZQ9hlSSEkqCJD4SAFswJQR1yoMfD3mzO3TEnY7LGthxPi",
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
                    "pubkey": "RWRqylWEtrAZQ9hlSSEkqCJD4SAFswJQR1yoMfD3mzO3TEnY7LGthxPi",
                    "updates": "stable",
                    "targets": {"testtarget/testsubtarget": "testarch"},
                },
            },
        }
    )

    return mock_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8001)


@pytest.fixture
def upstream(httpserver):
    base_url = "/snapshots/targets/testtarget/testsubtarget"
    upstream_path = Path("./tests/upstream/snapshots/targets/testtarget/testsubtarget/")
    expected_file_requests = [
        "sha256sums.sig",
        "sha256sums",
        "openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64.tar.xz",
    ]

    for f in expected_file_requests:
        httpserver.expect_request(f"{base_url}/{f}").respond_with_data(
            (upstream_path / f).read_bytes(),
            headers={"Last-Modified": "Thu, 19 Mar 2020 20:27:41 GMT"},
        )

    httpserver.check_assertions()
