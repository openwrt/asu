from prometheus_client import REGISTRY


def test_stats_image_builds(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'builds_total{profile="testprofile",target="testtarget/testsubtarget",version="1.2.3"} 1.0'
        in response.get_data(as_text=True)
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
    assert response.status == "200 OK"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'builds_total{profile="testprofile",target="testtarget/testsubtarget",version="1.2.3"} 2.0'
        in response.get_data(as_text=True)
    )


def test_stats_cache(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert "cache_hits 0.0" in response.get_data(as_text=True)

    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert "cache_hits 1.0" in response.get_data(as_text=True)


def test_stats_clients_luci(client):
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

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'clients_total{name="luci",version="git-22.073.39928-701ea94"} 1.0'
        in response.get_data(as_text=True)
    )


def test_stats_clients_unknown(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
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


def test_stats_clients_auc(client):
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

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'clients_total{name="auc",version="0.3.2"} 1.0' in response.get_data(
        as_text=True
    )


def test_stats_clients_auc_possible_new_format(client):
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

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'clients_total{name="auc",version="0.3.2"} 1.0' in response.get_data(
        as_text=True
    )
