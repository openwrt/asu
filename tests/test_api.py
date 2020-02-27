def test_api_version(client):
    response = client.get("/api/versions")
    assert response.json == {
        "SNAPSHOT": {
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
        }
    }


def test_api_build(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="8devices_carambola",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "0222f0cd9290"


def test_api_build_get(client):
    client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="8devices_carambola",
            packages=["test1", "test2"],
        ),
    )
    response = client.get("/api/build/0222f0cd9290")
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "0222f0cd9290"


def test_api_build_get_not_found(client):
    response = client.get("/api/build/testtesttest")
    assert response.status == "404 NOT FOUND"


def test_api_build_get_no_post(client):
    response = client.post("/api/build/0222f0cd9290")
    assert response.status == "405 METHOD NOT ALLOWED"


def test_api_build_empty_packages(client):
    response = client.post(
        "/api/build", json=dict(version="SNAPSHOT", profile="8devices_carambola")
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "5bac6cb8321f"


def test_api_build_empty_request(client):
    response = client.post("/api/build")
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("status") == "bad_request"


def test_api_build_needed(client):
    response = client.post("/api/build", json=dict(profile="8devices_carambola"))
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Missing version"
    assert response.json.get("status") == "bad_request"
    response = client.post("/api/build", json=dict(version="SNAPSHOT"))
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Missing profile"
    assert response.json.get("status") == "bad_request"


def test_api_build_bad_distro(client):
    response = client.post(
        "/api/build",
        json=dict(
            distro="Foobar",
            version="SNAPSHOT",
            profile="8devices_carambola",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unknown distro: Foobar"
    assert response.json.get("status") == "bad_distro"


def test_api_build_bad_version(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="Foobar", profile="8devices_carambola", packages=["test1", "test2"]
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unknown version: Foobar"
    assert response.json.get("status") == "bad_version"


def test_api_build_bad_profile(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="Foobar", packages=["test1", "test2"]),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unknown profile: Foobar"
    assert response.json.get("status") == "bad_profile"


def test_api_build_bad_packages(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="8devices_carambola", packages=["test4"]),
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json.get("message") == "Unknown package(s): test4"
    assert response.json.get("status") == "bad_packages"
