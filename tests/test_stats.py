import time
from fakeredis import FakeStrictRedis

build_config_1 = dict(
    version="1.2.3",
    target="testtarget/testsubtarget",
    profile="testprofile",
    packages=["test1"],
)

build_config_2 = dict(
    version="1.2.3",
    target="testtarget/testsubtarget",
    profile="testprofile",
    packages=["test1", "test2"],
)


class Stats:
    def __init__(self, redis_server: FakeStrictRedis):
        self.ts = redis_server.ts()

    def cache(self, type):
        return self.ts.mrange("-", "+", filters=[f"stats=cache-{type}"])

    def client(self, tag):
        clients = self.ts.mrange("-", "+", filters=["stats=clients"])
        if not clients:
            return []
        return clients[0][f"stats:clients:{tag}"]

    def build(self, tag):
        builds = self.ts.mrange("-", "+", filters=["stats=builds"])
        if not builds:
            return []
        return builds[0][f"stats:builds:{tag}"]


def test_stats_image_builds(client, redis_server: FakeStrictRedis):
    stats = Stats(redis_server)
    assert len(stats.build("1.2.3:testtarget/testsubtarget:testprofile")) == 0

    response = client.post("/api/v1/build", json=build_config_1)
    assert response.status_code == 200
    assert len(stats.build("1.2.3:testtarget/testsubtarget:testprofile")[1]) == 1


def test_stats_cache(client, redis_server: FakeStrictRedis):
    stats = Stats(redis_server)

    assert len(stats.cache("hits")) == 0
    assert len(stats.cache("misses")) == 0

    response = client.post("/api/v1/build", json=build_config_2)
    assert response.status_code == 200
    assert len(stats.cache("hits")) == 0
    assert len(stats.cache("misses")[0]["stats:cache-misses"][1]) == 1

    response = client.post("/api/v1/build", json=build_config_2)
    assert response.status_code == 200
    assert len(stats.cache("hits")[0]["stats:cache-hits"][1]) == 1
    assert len(stats.cache("misses")[0]["stats:cache-misses"][1]) == 1

    time.sleep(1)  # Ensure timestamp is on next second.
    response = client.post("/api/v1/build", json=build_config_2)
    assert response.status_code == 200
    assert len(stats.cache("hits")[0]["stats:cache-hits"][1]) == 2
    assert len(stats.cache("misses")[0]["stats:cache-misses"][1]) == 1


def test_stats_clients_luci(client, redis_server: FakeStrictRedis):
    asu_client = "luci/git-22.073.39928-701ea94"

    stats = Stats(redis_server)
    assert len(stats.client(asu_client)) == 0

    response = client.post(
        "/api/v1/build", json=dict(client=asu_client, **build_config_1)
    )
    assert response.status_code == 200
    assert len(stats.client(asu_client)[1]) == 1


def test_stats_clients_unknown(client, redis_server: FakeStrictRedis):
    asu_client = "unknown/0"

    stats = Stats(redis_server)
    assert len(stats.client(asu_client)) == 0

    response = client.post("/api/v1/build", json=build_config_2)
    assert response.status_code == 200
    assert len(stats.client(asu_client)[1]) == 1


def test_stats_clients_auc(client, redis_server: FakeStrictRedis):
    asu_client = "auc/0.3.2"

    stats = Stats(redis_server)
    assert len(stats.client(asu_client)) == 0

    response = client.post(
        "/api/v1/build", json=build_config_2, headers={"User-Agent": "auc (0.3.2)"}
    )
    assert response.status_code == 200
    assert len(stats.client(asu_client)[1]) == 1


def test_stats_clients_auc_possible_new_format(client, redis_server: FakeStrictRedis):
    asu_client = "auc/0.3.2"

    stats = Stats(redis_server)
    assert len(stats.client(asu_client)) == 0

    response = client.post(
        "/api/v1/build", json=build_config_2, headers={"User-Agent": asu_client}
    )
    assert response.status_code == 200
    assert len(stats.client(asu_client)[1]) == 1
