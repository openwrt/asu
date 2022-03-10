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
    assert response.json.get("request_hash") == "1d6d1b2addd0fa2ed47ae2a0662c3266"

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
    assert response.json.get("request_hash") == "f2f873d412c45a0b0e8f0bcdcecd3c19"

    response = client.get("/metrics")
    print(response.get_data(as_text=True))
    assert (
        'builds_total{branch="TESTVERSION",profile="testprofile",target="testtarget/testsubtarget",version="TESTVERSION"} 2.0'
        in response.get_data(as_text=True)
    )
