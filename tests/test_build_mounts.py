"""Test build file injection logic (keys, repos, defaults).

Tests verify that _make_tar produces correct archives and that
inject_files constructs the right file trees for the container.
"""

import tarfile
from io import BytesIO
from unittest.mock import MagicMock

from asu.build import _make_tar, inject_files
from asu.build_request import BuildRequest


def _extract_tar(data: bytes) -> dict[str, str]:
    """Helper: extract tar bytes into {name: content} dict."""
    result = {}
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                result[member.name] = tar.extractfile(member).read().decode("utf-8")
    return result


def test_make_tar_single_file():
    data = _make_tar({"hello.txt": "world"})
    files = _extract_tar(data)
    assert files == {"hello.txt": "world"}


def test_make_tar_multiple_files():
    data = _make_tar(
        {
            "a.txt": "aaa",
            "sub/b.txt": "bbb",
        }
    )
    files = _extract_tar(data)
    assert files["a.txt"] == "aaa"
    assert files["sub/b.txt"] == "bbb"


def test_make_tar_binary_content():
    data = _make_tar({"bin.dat": b"\x00\x01\x02"})
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        content = tar.extractfile("bin.dat").read()
    assert content == b"\x00\x01\x02"


def test_make_tar_empty():
    data = _make_tar({})
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        assert tar.getmembers() == []


def test_inject_files_no_extras():
    """No keys, repos, or defaults — nothing should be injected."""
    container = MagicMock()
    request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
    )
    inject_files(container, request)
    container.put_archive.assert_not_called()


def test_inject_files_with_defaults():
    container = MagicMock()
    request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        defaults="echo hello",
    )
    inject_files(container, request)
    container.put_archive.assert_called_once()

    call_args = container.put_archive.call_args
    assert call_args[0][0] == "/builder/"
    files = _extract_tar(call_args[0][1])
    assert "asu-files/etc/uci-defaults/99-asu-defaults" in files
    assert files["asu-files/etc/uci-defaults/99-asu-defaults"] == "echo hello"


def test_inject_files_with_repositories():
    container = MagicMock()
    request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        repositories={},
    )
    inject_files(container, request)
    container.put_archive.assert_not_called()


def test_inject_files_with_keys():
    container = MagicMock()
    # Valid usign public key (base64 of 2-byte pkalg + 8-byte keynum + 32-byte pubkey)
    import base64

    key_data = base64.b64encode(b"\x00" * 42).decode()
    request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        repository_keys=[key_data],
    )
    inject_files(container, request)
    container.put_archive.assert_called_once()

    call_args = container.put_archive.call_args
    assert call_args[0][0] == "/builder/"
    files = _extract_tar(call_args[0][1])
    # Should have one key file under keys/
    key_files = [f for f in files if f.startswith("keys/")]
    assert len(key_files) == 1
    assert key_data in files[key_files[0]]


def test_inject_files_defaults_and_keys():
    """Multiple inject types should result in multiple put_archive calls."""
    container = MagicMock()
    import base64

    key_data = base64.b64encode(b"\x00" * 42).decode()
    request = BuildRequest(
        version="1.2.3",
        target="testtarget/testsubtarget",
        profile="testprofile",
        defaults="echo test",
        repository_keys=[key_data],
    )
    inject_files(container, request)
    assert container.put_archive.call_count == 2
