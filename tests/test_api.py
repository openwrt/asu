import pytest
from fastapi.testclient import TestClient

from asu.config import settings


def test_api_build(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["manifest"]["test1"] == "1.0"


def test_api_build_version_code(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            version_code="r12647-cb44ab4f5d",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200


def test_api_build_rootfs_size(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            rootfs_size_mb=100,
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["build_cmd"][6] == "ROOTFS_PARTSIZE=100"


def test_api_build_version_code_bad(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            version_code="some-bad-version-code",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200


def test_api_build_diff_packages(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            diff_packages=True,
        ),
    )

    assert response.status_code == 200

    data = response.json()

    # TODO shorten for testing
    assert (
        data["build_cmd"][3]
        == "PACKAGES=-base-files -busybox -dnsmasq -dropbear -firewall -fstools -ip6tables -iptables -kmod-ath9k -kmod-gpio-button-hotplug -kmod-ipt-offload -kmod-usb-chipidea2 -kmod-usb-storage -kmod-usb2 -libc -libgcc -logd -mtd -netifd -odhcp6c -odhcpd-ipv6only -opkg -ppp -ppp-mod-pppoe -swconfig -uboot-envtools -uci -uclient-fetch -urandom-seed -urngd -wpad-basic test1 test2"
    )


def test_api_latest_default(client):
    response = client.get("/api/v1/latest", follow_redirects=False)
    assert response.status_code == 301


def test_api_overview(client):
    response = client.get("/api/v1/overview", follow_redirects=False)
    assert response.status_code == 301


def test_api_build_mapping(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 200


def test_api_build_mapping_abi(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1-1", "test2"],
        ),
    )
    assert response.status_code == 200


def test_api_build_bad_target(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtargetbad",
            profile="testvendor,testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 400
    data = response.json()

    assert data.get("detail") == "Unsupported target: testtarget/testsubtargetbad"


def test_api_build_get(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    data = response.json()
    request_hash = data["request_hash"]
    response = client.get(f"/api/v1/build/{request_hash}")
    assert response.status_code == 200
    data = response.json()
    assert data["request_hash"] == request_hash


def test_api_build_packages_versions(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    data = response.json()
    request_hash = data["request_hash"]
    response = client.get(f"/api/v1/build/{request_hash}")
    assert response.status_code == 200
    data = response.json()
    assert data["request_hash"] == request_hash


def test_api_build_packages_versions_bad(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages_versions={"test1": "0.0", "test2": "2.0"},
        ),
    )
    data = response.json()
    request_hash = data["request_hash"]
    response = client.get(f"/api/v1/build/{request_hash}")
    assert response.status_code == 500
    assert (
        data["detail"]
        == "Error: Impossible package selection: test1 version not as requested: 0.0 vs. 1.0"
    )


def test_api_build_packages_duplicate(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
            packages_versions={"test1": "1.0", "test2": "2.0"},
        ),
    )
    assert response.status_code == 200


def test_api_build_get_not_found(client):
    response = client.get("/api/v1/build/testtesttest")
    assert response.status_code == 404


def test_api_build_get_no_post(client):
    response = client.post("/api/v1/build/0222f0cd9290")
    assert response.status_code == 405


def test_api_build_empty_packages_list(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=[],
        ),
    )
    assert response.status_code == 200


def test_api_build_withouth_packages_list(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
        ),
    )
    assert response.status_code == 200


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
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Unsupported profile: testprofile"


def test_api_build_prerelease_rc(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="21.02.7",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Unsupported profile: testprofile"


def test_api_build_bad_packages_str(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages="testpackage",
        ),
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {
            "input": "testpackage",
            "loc": ["body", "packages"],
            "msg": "Input should be a valid list",
            "type": "list_type",
        }
    ]


def test_api_build_empty_request(client):
    response = client.post("/api/v1/build")
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {"input": None, "loc": ["body"], "msg": "Field required", "type": "missing"}
    ]


@pytest.mark.slow
def test_api_build_real_x86(app):
    client = app.test_client()
    app.config["UPSTREAM_URL"] = "https://downloads.openwrt.org"
    response = client.post(
        "/api/v1/build",
        json=dict(
            target="x86/64",
            version="21.02.7",
            packages=["tmux", "vim"],
            profile="some_random_cpu_which_doesnt_exists_as_profile",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "generic"

    response = client.post(
        "/api/v1/build",
        json=dict(
            target="x86/64",
            version="21.02.7",
            packages=["tmux", "vim"],
            profile="some_random_cpu_which_doesnt_exists_as_profile",
            filesystem="ext4",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "generic"


@pytest.mark.slow
def test_api_build_real_ath79(app):
    client = app.test_client()
    app.config["UPSTREAM_URL"] = "https://downloads.openwrt.org"
    response = client.post(
        "/api/v1/build",
        json=dict(
            target="ath79/generic",
            version="21.02.7",
            packages=["tmux", "vim"],
            profile="tplink_tl-wdr4300-v1",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tplink_tl-wdr4300-v1"

    response = client.post(
        "/api/v1/build",
        json=dict(
            target="ath79/generic",
            version="21.02.7",
            packages=["tmux", "vim"],
            profile="tplink_tl-wdr4300-v1",
            filesystem="squashfs",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tplink_tl-wdr4300-v1"


def test_api_build_needed(client):
    response = client.post(
        "/api/v1/build",
        json=dict(profile="testprofile", target="testtarget/testsubtarget"),
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {
            "input": {"profile": "testprofile", "target": "testtarget/testsubtarget"},
            "loc": ["body", "version"],
            "msg": "Field required",
            "type": "missing",
        }
    ]
    response = client.post(
        "/api/v1/build",
        json=dict(version="1.2.3", target="testtarget/testsubtarget"),
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {
            "type": "missing",
            "loc": ["body", "profile"],
            "msg": "Field required",
            "input": {"version": "1.2.3", "target": "testtarget/testsubtarget"},
        }
    ]

    response = client.post(
        "/api/v1/build", json=dict(version="1.2.3", profile="testprofile")
    )
    assert response.status_code == 422
    data = response.json()
    print(data)
    assert data["detail"] == [
        {
            "type": "missing",
            "loc": ["body", "target"],
            "msg": "Field required",
            "input": {"version": "1.2.3", "profile": "testprofile"},
        }
    ]


def test_api_build_bad_distro(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            distro="Foobar",
            target="testtarget/testsubtarget",
            version="1.2.3",
            profile="testprofile",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Unsupported distro: Foobar"


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
    assert response.status_code == 400
    data = response.json()
    print(data)
    assert data["detail"] == "Unsupported branch: 10.10.10"


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
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Unsupported version: 19.07.2"


def test_api_build_bad_profile(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="Foobar",
            packages=["test1", "test2"],
        ),
    )
    assert response.status_code == 400

    data = response.json()
    assert data["detail"] == "Unsupported profile: Foobar"


def test_api_build_defaults_empty(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="",
        ),
    )
    assert response.status_code == 200


def test_api_build_defaults_filled_not_allowed(client):
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="echo",
        ),
    )

    data = response.json()
    print(data)

    print(response.status_code)
    assert response.status_code == 400


def test_api_build_defaults_filled_allowed(app):
    settings.allow_defaults = True
    client = TestClient(app)
    response = client.post(
        "/api/v1/build",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            defaults="echo",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["request_hash"] == "583290466ebafc7dbfa2324a4ea12df0"
