from fakeredis import FakeStrictRedis


def test_stats_image_builds(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=builds"])[0][
                "stats:builds:1.2.3:testtarget/testsubtarget:testprofile"
            ][1]
        )
        == 1
    )

    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1"],
        ),
    )
    assert response.status_code == 200

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=builds"])[0][
                "stats:builds:1.2.3:testtarget/testsubtarget:testprofile"
            ][1]
        )
        == 2
    )


def test_stats_cache(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=cache-misses"])[0][
                "stats:cache-misses"
            ][1]
        )
        == 1
    )

    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200

    assert (
        len(ts.mrange("-", "+", filters=["stats=cache-hits"])[0]["stats:cache-hits"][1])
        == 1
    )


def test_stats_clients_luci(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            client="luci/git-22.073.39928-701ea94",
        ),
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=clients"])[0][
                "stats:clients:luci/git-22.073.39928-701ea94"
            ][1]
        )
        == 1
    )


def test_stats_clients_unknown(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=clients"])[0][
                "stats:clients:unknown/0"
            ][1]
        )
        == 1
    )


def test_stats_clients_auc(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
        headers={"User-Agent": "auc (0.3.2)"},
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=clients"])[0][
                "stats:clients:auc/0.3.2"
            ][1]
        )
        == 1
    )


def test_stats_clients_auc_possible_new_format(client, redis_server: FakeStrictRedis):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
        headers={"User-Agent": "auc/0.3.2"},
    )
    assert response.status_code == 200

    ts = redis_server.ts()

    assert (
        len(
            ts.mrange("-", "+", filters=["stats=clients"])[0][
                "stats:clients:auc/0.3.2"
            ][1]
        )
        == 1
    )
