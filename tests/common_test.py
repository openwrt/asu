from pathlib import PosixPath
import os
import tempfile
from pathlib import Path

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

    assert get_request_hash(request) == "ce7c88df2626"


def test_get_request_hash_diff_packages():
    request = {
        "distro": "test",
        "version": "test",
        "profile": "test",
        "package_hash": get_packages_hash(["test"]),
        "diff_packages": True,
    }

    assert get_request_hash(request) == "bbe753d61568"


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
