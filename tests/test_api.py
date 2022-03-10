import pytest


def test_api_version(client, app):
    response = client.get("/api/branches")
    assert response.status == "200 OK"


def test_api_build(client, upstream):
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


def test_api_latest_default(client):
    response = client.get("/api/latest")
    assert response.status == "302 FOUND"


def test_api_build_mapping(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "1ead618e56444f77b93ec880429ccb17"


def test_api_build_mapping_abi(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testvendor,testprofile",
            packages=["test1-1", "test2"],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "4ee24befb7cb0ccda410dd2e37423dcc"


def test_api_build_bad_target(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtargetbad",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert (
        response.json.get("detail") == "Unsupported target: testtarget/testsubtargetbad"
    )


def test_api_build_get(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.json["request_hash"] == "1d6d1b2addd0fa2ed47ae2a0662c3266"
    response = client.get("/api/v1/build/1d6d1b2addd0fa2ed47ae2a0662c3266")
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "1d6d1b2addd0fa2ed47ae2a0662c3266"


def test_api_build_packages_versions(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    assert response.json["request_hash"] == "1d7db3e36d6cd96fb321a260d077698c"
    response = client.get("/api/v1/build/1d7db3e36d6cd96fb321a260d077698c")
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "1d7db3e36d6cd96fb321a260d077698c"


def test_api_build_packages_duplicate(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    assert response.status == "200 OK"


def test_api_build_get_not_found(client):
    response = client.get("/api/v1/build/testtesttest")
    assert response.status == "404 NOT FOUND"


def test_api_build_get_no_post(client):
    response = client.post("/api/v1/build/0222f0cd9290")
    assert response.status == "405 METHOD NOT ALLOWED"


def test_api_build_empty_packages_list(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=[],
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "7da30651a23d18e244001b5434a05ba6"


def test_api_build_withouth_packages_list(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "7da30651a23d18e244001b5434a05ba6"


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
            version="21.02.0",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "Unsupported profile: testprofile"


def test_api_build_bad_packages_str(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages="testpackage",
        ),
    )
    assert response.status == "400 BAD REQUEST"
    assert (
        response.json.get("detail")
        == "'testpackage' is not of type 'array' - 'packages'"
    )


def test_api_build_empty_request(client):
    response = client.post("/api/v1/build")
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "None is not of type 'object'"


@pytest.mark.slow
def test_api_build_real_x86(app):
    client = app.test_client()
    app.config["UPSTREAM_URL"] = "https://downloads.openwrt.org"
    response = client.post(
        "/api/v1/build",
        json=dict(
            target="x86/64",
            version="SNAPSHOT",
            packages=["tmux", "vim"],
            profile="some_random_cpu_which_doesnt_exists_as_profile",
        ),
    )

    assert response.status == "200 OK"
    assert response.json.get("id") == "generic"


@pytest.mark.slow
def test_api_build_real_ath79(app):
    client = app.test_client()
    app.config["UPSTREAM_URL"] = "https://downloads.openwrt.org"
    response = client.post(
        "/api/v1/build",
        json=dict(
            target="ath79/generic",
            version="SNAPSHOT",
            packages=["tmux", "vim"],
            profile="tplink_tl-wdr4300-v1",
        ),
    )

    assert response.status == "200 OK"
    assert response.json.get("id") == "tplink_tl-wdr4300-v1"


def test_api_build_needed(client):
    response = client.post(
        "/api/v1/build",
        json=dict(profile="testprofile", target="testtarget/testsubtarget"),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'version' is a required property"
    assert response.json.get("title") == "Bad Request"
    response = client.post(
        "/api/v1/build",
        json=dict(version="TESTVERSION", target="testtarget/testsubtarget"),
    )
    assert response.status == "400 BAD REQUEST"
    assert response.json.get("detail") == "'profile' is a required property"
    assert response.json.get("title") == "Bad Request"
    response = client.post(
        "/api/v1/build", json=dict(version="TESTVERSION", profile="testprofile")
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
            version="TESTVERSION",
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
            version="TESTVERSION",
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
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test4"],
        ),
    )
    assert response.json.get("detail") == "Unsupported package(s): test4"
    assert response.status == "422 UNPROCESSABLE ENTITY"
