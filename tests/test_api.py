def test_api_version(client, app):
    response = client.get("/api/versions")
    assert response.json == app.config["VERSIONS"]


def test_api_build(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "0af0c1a9ea31"

def test_api_build_mapping(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "cfe4b87e4ec7"


def test_api_build_get(client):
    client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    response = client.get("/api/build/0af0c1a9ea31")
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "0af0c1a9ea31"


def test_api_build_get_not_found(client):
    response = client.get("/api/build/testtesttest")
    assert response.status == "404 NOT FOUND"


def test_api_build_get_no_post(client):
    response = client.post("/api/build/0222f0cd9290")
    assert response.status == "405 METHOD NOT ALLOWED"


def test_api_build_empty_packages_list(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="testprofile", packages=[]),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "a86ba552b5f6"


def test_api_build_withouth_packages_list(client):
    response = client.post(
        "/api/build", json=dict(version="SNAPSHOT", profile="testprofile")
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "a86ba552b5f6"


def test_api_build_bad_packages_str(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT", profile="testprofile", packages="testpackage"
        ),
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"
    assert response.json.get("status") == "bad_packages"


def test_api_build_empty_request(client):
    response = client.post("/api/build")
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("status") == "bad_request"


def test_api_build_needed(client):
    response = client.post("/api/build", json=dict(profile="testprofile"))
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
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported distro: foobar"
    assert response.json.get("status") == "bad_distro"


def test_api_build_bad_version(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="Foobar", profile="testprofile", packages=["test1", "test2"]
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported version: foobar"
    assert response.json.get("status") == "bad_version"


def test_api_build_bad_profile(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="Foobar", packages=["test1", "test2"]),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported profile: Foobar"
    assert response.json.get("status") == "bad_profile"


def test_api_build_bad_packages(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="testprofile", packages=["test4"]),
    )
    assert response.json.get("message") == "Unsupported package(s): test4"
    assert response.json.get("status") == "bad_packages"
    assert response.status == "422 UNPROCESSABLE ENTITY"
