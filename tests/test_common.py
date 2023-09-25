import os
import tempfile
from os import getenv
from pathlib import Path, PosixPath

from asu.common import *


def test_get_str_hash():
    assert get_str_hash("test", 12) == "9f86d081884c"


def test_get_file_hash():
    file_fd, file_path = tempfile.mkstemp()
    os.write(file_fd, b"test")

    assert get_file_hash(file_path).startswith("9f86d081884c")

    os.close(file_fd)
    os.unlink(file_path)


def test_get_packages_hash():
    assert get_packages_hash(["test1", "test2"]) == "57aab5949a36"


def test_get_request_hash():
    request = {
        "distro": "test",
        "version": "test",
        "profile": "test",
        "package_hash": get_packages_hash(["test"]),
    }


def test_diff_packages():
    assert diff_packages({"test1"}, {"test1", "test2"}) == ["-test2", "test1"]
    assert diff_packages({"test1"}, {"test1"}) == ["test1"]
    assert diff_packages({"test1"}, {"test2", "test3"}) == ["-test2", "-test3", "test1"]
    assert diff_packages({"test1"}, {"test2", "-test3"}) == [
        "-test2",
        "-test3",
        "test1",
    ]


def test_fingerprint_pubkey_usign():
    pub_key = "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89"
    assert fingerprint_pubkey_usign(pub_key) == "ab1df166947b2551"


def test_verify_usign():
    sig = b"\nRWSrHfFmlHslUQ9dCB1AJr/PoIIbBJJKtofZ5frLOuG03SlwAwgU1tYOaJs2eVGdo1C8S9LNcMBLPIfDDCWSdrLK3WJ6JV6HNQM="
    msg_fd, msg_path = tempfile.mkstemp()
    sig_fd, sig_path = tempfile.mkstemp()
    os.write(msg_fd, b"test\n")
    os.write(sig_fd, sig)

    pub_key = "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89"
    pub_key_bad = "rWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SXXX"

    assert verify_usign(Path(sig_path), Path(msg_path), pub_key)
    assert not verify_usign(Path(sig_path), Path(msg_path), pub_key_bad)

    os.close(msg_fd)
    os.close(sig_fd)
    os.unlink(msg_path)
    os.unlink(sig_path)


def test_remove_prefix():
    assert remove_prefix("test", "test") == ""
    assert remove_prefix("+test", "+") == "test"
    assert remove_prefix("++test", "+") == "+test"


def test_get_version_container_tag():
    assert get_container_version_tag("1.0.0") == "v1.0.0"
    assert get_container_version_tag("SNAPSHOT") == "master"
    assert get_container_version_tag("1.0.0-SNAPSHOT") == "openwrt-1.0.0"
    assert get_container_version_tag("23.05.0-rc3") == "v23.05.0-rc3"


def test_check_manifest():
    assert check_manifest({"test": "1.0"}, {"test": "1.0"}) == None
    assert (
        check_manifest({"test": "1.0"}, {"test": "2.0"})
        == "Impossible package selection: test version not as requested: 2.0 vs. 1.0"
    )
    assert (
        check_manifest({"test": "1.0"}, {"test2": "1.0"})
        == "Impossible package selection: test2 not in manifest"
    )


def test_run_container():
    podman = PodmanClient().from_env()
    returncode, stdout, stderr = run_container(
        podman,
        "ghcr.io/openwrt/imagebuilder:testtarget-testsubtarget-v1.2.3",
        ["make", "info"],
    )

    assert returncode == 0
    assert "testtarget/testsubtarget" in stdout
