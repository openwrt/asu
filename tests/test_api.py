def test_api_version(client, app):
    response = client.get("/api/branches")
    assert response.status == "200 OK"


def test_api_build(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "e360f833a1914b2f82844fa6d33f0d7f"


def test_api_latest_default(client):
    response = client.get("/api/latest")
    assert response.status == "302 FOUND"


def test_api_build_mapping(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "19bb42f198c975cfbaf8a2ec241b7580"


def test_api_build_mapping_abi(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testvendor,testprofile",
            packages=["test1-1", "test2"],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "7d099fb07fb35a55de091ad2a148fca5"


def test_api_build_bad_target(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtargetbad",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert (
        response.json.get("detail")
        == "Unsupported target: testtarget/testsubtargetbad"
    )


def test_api_build_get(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.json["request_hash"] == "e360f833a1914b2f82844fa6d33f0d7f"
    response = client.get("/api/v1/build/e360f833a1914b2f82844fa6d33f0d7f")
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "e360f833a1914b2f82844fa6d33f0d7f"


def test_api_build_packages_versions(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    assert response.json["request_hash"] == "552b9e328888629e83649256497f981d"
    response = client.get("/api/v1/build/552b9e328888629e83649256497f981d")
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "552b9e328888629e83649256497f981d"


def test_api_build_packages_duplicate(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    assert response.status == "202 ACCEPTED"


def test_api_build_get_not_found(client):
    response = client.get("/api/v1/build/testtesttest")
    assert response.status == "404 NOT FOUND"


def test_api_build_get_no_post(client):
    response = client.post("/api/v1/build/0222f0cd9290")
    assert response.status == "405 METHOD NOT ALLOWED"


def test_api_build_empty_packages_list(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=[],
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "66cb932c37a4a2d1b012db4eb5286cf0"


def test_api_build_withouth_packages_list(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
        ),
    )
    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "66cb932c37a4a2d1b012db4eb5286cf0"


def test_api_build_prerelease_snapshot(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="21.02-SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported profile: testprofile"


def test_api_build_prerelease_rc(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="21.02.0-rc1",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported profile: testprofile"


def test_api_build_bad_packages_str(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages="testpackage",
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'testpackage' is not of type 'array' - 'packages'"


def test_api_build_empty_request(client):
    response = client.post("/api/v1/build")
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "None is not of type 'object'"


def test_api_build_x86(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            target="x86/64",
            version="SNAPSHOT",
            profile="some_random_cpu_which_doesnt_exists_as_profile",
        ),
    )

    assert response.status == "202 ACCEPTED"
    assert response.json.get("detail") == "queued"
    assert response.json.get("request_hash") == "1fda145d439f33b0e8e671115bd0bd66"


def test_api_build_needed(client):
    response = client.post(
        "/api/v1/build",
        json=dict(profile="testprofile", target="testtarget/testsubtarget"),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'version' is a required property"
    assert response.json.get("title") == "Bad Request"
    response = client.post(
        "/api/v1/build", json=dict(version="SNAPSHOT", target="testtarget/testsubtarget")
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'profile' is a required property"
    assert response.json.get("title") == "Bad Request"
    response = client.post(
        "/api/v1/build", json=dict(version="SNAPSHOT", profile="testprofile")
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'target' is a required property"
    assert response.json.get("title") == "Bad Request"


def test_api_build_bad_distro(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            distro="Foobar",
            target="testtarget/testsubtarget",
            version="SNAPSHOT",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported distro: Foobar"


def test_api_build_bad_branch(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="10.10.10",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported branch: 10.10.10"


def test_api_build_bad_version(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="19.07.2",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported version: 19.07.2"


def test_api_build_bad_profile(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="Foobar",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported profile: Foobar"


def test_api_build_bad_packages(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="SNAPSHOT",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test4"],
        ),
    )
    assert response.json.get("detail") == "Unsupported package(s): test4"
    assert response.status == "422 UNPROCESSABLE ENTITY"
