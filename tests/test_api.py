def test_api_version(client, app):
    response = client.get("/api/branches")
    branches = {}
    for branch in app.config["BRANCHES"]:
        if branch["enabled"]:
            branches[branch["name"]] = branch
    assert response.json == branches


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
    assert response.json.get("request_hash") == "3128aff5c6db"


def test_api_latest_default(client):
    response = client.get("/api/latest")
    assert response.json == {"latest": ["19.07.6"]}
    assert response.status == "200 OK"


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
    assert response.json.get("request_hash") == "d0318d0bba8d"


def test_api_build_get(client):
    client.post(
        "/api/build",
        json=dict(
            version="SNAPSHOT",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    response = client.get("/api/build/3128aff5c6db")
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "3128aff5c6db"


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
    assert response.json.get("request_hash") == "c6022275d623"


def test_api_build_withouth_packages_list(client):
    response = client.post(
        "/api/build", json=dict(version="SNAPSHOT", profile="testprofile")
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("status") == "queued"
    assert response.json.get("request_hash") == "c6022275d623"


def test_api_build_prerelease(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="21.02-SNAPSHOT", profile="testprofile", packages=["test1", "test2"]
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported profile: testprofile"
    assert response.json.get("status") == "bad_profile"


def test_api_build_bad_packages_str(client):
    response = client.post(
        "/api/build",
        json=dict(version="SNAPSHOT", profile="testprofile", packages="testpackage"),
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
    assert response.json.get("message") == "Unsupported distro: Foobar"
    assert response.json.get("status") == "bad_distro"


def test_api_build_bad_branch(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="10.10.10", profile="testprofile", packages=["test1", "test2"]
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported branch: 10.10.10"
    assert response.json.get("status") == "bad_branch"


def test_api_build_bad_version(client):
    response = client.post(
        "/api/build",
        json=dict(
            version="19.07.2", profile="testprofile", packages=["test1", "test2"]
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("message") == "Unsupported version: 19.07.2"
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
