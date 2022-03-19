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
    assert response.json.get("request_hash") == "33377fbd91c50c4236343f1dfd67f9ae"

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
    assert response.json.get("request_hash") == "0f959015710e622bc42c088951b7585c"

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
    assert response.json.get("request_hash") == "33377fbd91c50c4236343f1dfd67f9ae"

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
    assert response.json.get("request_hash") == "33377fbd91c50c4236343f1dfd67f9ae"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert "cache_hits 1.0" in response.get_data(as_text=True)


def test_stats_extra_packages(client, upstream):
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
    assert response.json.get("request_hash") == "33377fbd91c50c4236343f1dfd67f9ae"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'extra_package_installs{package="test1"} 1.0' in response.get_data(
        as_text=True
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
    assert response.json.get("request_hash") == "0f959015710e622bc42c088951b7585c"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert 'extra_package_installs{package="test1"} 2.0' in response.get_data(
        as_text=True
    )
