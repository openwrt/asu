from prometheus_client import REGISTRY


def test_stats_image_builds(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "7eb856bfaccac42d16ba5ecfa6b2ebe5"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'builds_total{branch="TESTVERSION",profile="testprofile",target="testtarget/testsubtarget",version="TESTVERSION"} 1.0'
        in response.get_data(as_text=True)
    )

    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "3729c16c93b893121be36f99809f8354"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'builds_total{branch="TESTVERSION",profile="testprofile",target="testtarget/testsubtarget",version="TESTVERSION"} 2.0'
        in response.get_data(as_text=True)
    )


def test_stats_cache(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "7eb856bfaccac42d16ba5ecfa6b2ebe5"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert "cache_hits 0.0" in response.get_data(as_text=True)

    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "7eb856bfaccac42d16ba5ecfa6b2ebe5"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert "cache_hits 1.0" in response.get_data(as_text=True)


def test_stats_clients_luci(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            client="luci/git-22.073.39928-701ea94",
        ),
    )

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'clients_total{name="luci",version="git-22.073.39928-701ea94"} 1.0'
        in response.get_data(as_text=True)
    )


def test_stats_clients_unknown(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'clients_total{name="unknown",version="0"} 1.0' in response.get_data(
        as_text=True
    )


def test_stats_clients_auc(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
        headers={"User-Agent": "auc (0.3.2)"},
    )

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'clients_total{name="auc",version="0.3.2"} 1.0' in response.get_data(
        as_text=True
    )


def test_stats_clients_auc_possible_new_format(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
        headers={"User-Agent": "auc/0.3.2"},
    )

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'clients_total{name="auc",version="0.3.2"} 1.0' in response.get_data(
        as_text=True
    )
