import pytest


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
    assert response.json.get("request_hash") == "df1dfbb6f6deca36b389e4b2917cb8f0"


def test_api_build_filesystem_ext4(app, upstream):
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="ext4",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "34df61de58ef879888f91d75ccd381f2"

    config = (
        app.config["CACHE_PATH"] / "cache/TESTVERSION/testtarget/testsubtarget/.config"
    ).read_text()
    assert "# CONFIG_TARGET_ROOTFS_SQUASHFS is not set" in config
    assert "CONFIG_TARGET_ROOTFS_EXT4FS=y" in config


def test_api_build_filesystem_squashfs(app, upstream):
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="squashfs",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "8f9718015c027664b0a8245e39f21d09"
    config = (
        app.config["CACHE_PATH"] / "cache/TESTVERSION/testtarget/testsubtarget/.config"
    ).read_text()
    assert "# CONFIG_TARGET_ROOTFS_EXT4FS is not set" in config
    assert "CONFIG_TARGET_ROOTFS_SQUASHFS=y" in config


def test_api_build_filesystem_empty(app, upstream):
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "df1dfbb6f6deca36b389e4b2917cb8f0"
    config = (
        app.config["CACHE_PATH"] / "cache/TESTVERSION/testtarget/testsubtarget/.config"
    ).read_text()
    assert "CONFIG_TARGET_ROOTFS_EXT4FS=y" in config
    assert "CONFIG_TARGET_ROOTFS_SQUASHFS=y" in config


def test_api_build_filesystem_reset(app, upstream):
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="ext4",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "34df61de58ef879888f91d75ccd381f2"

    assert (
        "# CONFIG_TARGET_ROOTFS_SQUASHFS is not set"
        in (
            app.config["CACHE_PATH"]
            / "cache/TESTVERSION/testtarget/testsubtarget/.config"
        ).read_text()
    )

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
    assert response.json.get("request_hash") == "df1dfbb6f6deca36b389e4b2917cb8f0"
    assert (
        "# CONFIG_TARGET_ROOTFS_SQUASHFS is not set"
        not in (
            app.config["CACHE_PATH"]
            / "cache/TESTVERSION/testtarget/testsubtarget/.config"
        ).read_text()
    )


def test_api_build_filesystem_bad(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="bad",
        ),
    )
    assert response.status == "400 BAD REQUEST"


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
    assert response.json.get("request_hash") == "697a3aa34dcc7e2577a69960287c3b9b"


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
    assert response.json.get("request_hash") == "4c1e7161dd3f0c4ca2ba04a65c6bf0fb"


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
    assert response.json["request_hash"] == "df1dfbb6f6deca36b389e4b2917cb8f0"
    response = client.get("/api/v1/build/df1dfbb6f6deca36b389e4b2917cb8f0")
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "df1dfbb6f6deca36b389e4b2917cb8f0"


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
    assert response.json["request_hash"] == "bb873a96483917da5b320a7a90b75985"
    response = client.get("/api/v1/build/bb873a96483917da5b320a7a90b75985")
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "bb873a96483917da5b320a7a90b75985"


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
    assert response.json.get("request_hash") == "c1175efc86abda8d1b03f38204e7dc02"


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
    assert response.json.get("request_hash") == "c1175efc86abda8d1b03f38204e7dc02"


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

    response = client.post(
        "/api/v1/build",
        json=dict(
            target="x86/64",
            version="SNAPSHOT",
            packages=["tmux", "vim"],
            profile="some_random_cpu_which_doesnt_exists_as_profile",
            filesystem="ext4",
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

    response = client.post(
        "/api/v1/build",
        json=dict(
            target="ath79/generic",
            version="SNAPSHOT",
            packages=["tmux", "vim"],
            profile="tplink_tl-wdr4300-v1",
            filesystem="squashfs",
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


def test_api_build_package_to_remove_diff_packages_false(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2", "package_to_remove"],
            diff_packages=False,
        ),
    )
    assert response.status == "422 UNPROCESSABLE ENTITY"


def test_api_build_cleanup(app, upstream):
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            filesystem="ext4",
        ),
    )
    assert response.status == "200 OK"
    assert not (
        app.config["CACHE_PATH"]
        / "cache/TESTVERSION/testtarget/testsubtarget"
        / "pseudo_kernel_build_dir/tmp/"
        / "fake_trash"
    ).exists()


def test_api_build_defaults_empty(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "c1175efc86abda8d1b03f38204e7dc02"


def test_api_build_defaults_filled_not_allowed(client, upstream):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="echo",
        ),
    )

    assert response.status == "400 BAD REQUEST"


def test_api_build_defaults_filled_allowed(app, upstream):
    app.config["ALLOW_DEFAULTS"] = True
    client = app.test_client()
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="TESTVERSION",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="echo",
        ),
    )
    assert response.status == "200 OK"
    assert response.json.get("request_hash") == "95850740d931c460d77f8de35f298b9a"
