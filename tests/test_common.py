import os
import tempfile
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

    assert get_request_hash(request) == "fe3a1358af58b6583c9f5a95b35c56a3"


def test_get_request_hash_diff_packages():
    request = {
        "distro": "test",
        "version": "test",
        "profile": "test",
        "package_hash": get_packages_hash(["test"]),
        "diff_packages": True,
    }

    assert get_request_hash(request) == "caaa8f25efadb5456f8fd32b5a4ba032"
