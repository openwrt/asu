import os
import tempfile
from pathlib import Path

import pytest
from urlpath import URL

from asu.imagebuilder import ImageBuilder, fingerprint_pubkey_usign, verify_usign


def test_imagebuilder_url_21023():
    ib = ImageBuilder()
    assert ib.imagebuilder_url == URL(
        "https://downloads.openwrt.org/releases/21.02.3/targets/x86/64"
    )


def test_imagebuilder_url_2102_SNAPSHOT():
    ib = ImageBuilder(version="21.02-SNAPSHOT")
    assert ib.imagebuilder_url == URL(
        "https://downloads.openwrt.org/releases/21.02-SNAPSHOT/targets/x86/64"
    )


def test_imagebuilder_url_snapshot():
    ib = ImageBuilder(version="SNAPSHOT")
    assert ib.imagebuilder_url == URL(
        "https://downloads.openwrt.org/snapshots/targets/x86/64"
    )


def test_get_sha256sums():
    ib = ImageBuilder(version="21.02.3")
    assert ib.get_sha256sums().splitlines()[0].endswith("*config.buildinfo")


def test_archive():
    ib = ImageBuilder(version="21.02.3")
    assert ib._get_archive_sum_name() == (
        "4f6e8c06471f92db0d9cf0168da7213291bb7d1da2197a307528152e02e658ae",
        "openwrt-imagebuilder-21.02.3-x86-64.Linux-x86_64.tar.xz",
    )


def test_archive_name():
    ib = ImageBuilder(version="21.02.3")
    assert ib.archive_name == "openwrt-imagebuilder-21.02.3-x86-64.Linux-x86_64.tar.xz"


def test_archive_sum():
    ib = ImageBuilder(version="21.02.3")
    assert (
        ib.archive_sum
        == "4f6e8c06471f92db0d9cf0168da7213291bb7d1da2197a307528152e02e658ae"
    )


# def test_download_21_02_3():
#     ib = ImageBuilder(version="21.02.3", upstream_url="downloads.cdn.openwrt.org")
#     ib.download()
#     assert (ib.cache / ib.archive_name).exists()


# def test_download_snapshot():
#     ib = ImageBuilder(version="SNAPSHOT", upstream_url="downloads.cdn.openwrt.org")
#     ib.download()
#     assert (ib.cache / ib.archive_name).exists()


def test_verify_signature_snapshot():
    ib = ImageBuilder(version="SNAPSHOT")
    assert ib.valid_signature()


def test_verify_signature_21_02_3():
    ib = ImageBuilder(version="21.02.3")
    assert ib.valid_signature()


def test_verify_signature_99_99_99():
    ib = ImageBuilder(version="99_99_99")
    with pytest.raises(Exception) as exc_info:
        ib.valid_signature()

    assert (
        str(exc_info.value)
        == "404 Client Error: Not Found for url: https://downloads.openwrt.org/releases/99_99_99/targets/x86/64/sha256sums.sig"
    )


def test_is_outdated(tmpdir):
    ib = ImageBuilder(version="21.02.3", cache=tmpdir)

    assert ib.is_outdated()

    ib.workdir.mkdir(parents=True, exist_ok=True)
    (ib.workdir / "Makefile").touch()
    os.utime(str(ib.workdir / "Makefile"), (0, 0))
    assert ib.is_outdated()

    os.utime(str(ib.workdir / "Makefile"), (2650340906, 2650340906))
    assert not ib.is_outdated()


# def test_setup(tmpdir):
#     ib = ImageBuilder(version="21.02.3", cache=tmpdir)
#     assert ib.setup() is None


def test_fingerprint_pubkey_usign():
    pub_key = "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89"
    assert fingerprint_pubkey_usign(pub_key) == "ab1df166947b2551"


def test_verify_usign():
    sig = "RWSrHfFmlHslUQ9dCB1AJr/PoIIbBJJKtofZ5frLOuG03SlwAwgU1tYOaJs2eVGdo1C8S9LNcMBLPIfDDCWSdrLK3WJ6JV6HNQM="

    pub_key = "RWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SU89"
    pub_key_bad = "rWSrHfFmlHslUcLbXFIRp+eEikWF9z1N77IJiX5Bt/nJd1a/x+L+SXXX"

    assert verify_usign(sig, "test\n", pub_key)
    assert not verify_usign(sig, "test\n", pub_key_bad)

def test_manifest():
    ib = ImageBuilder(version="21.02.3")
    # ib.setup()
    ib.manifest("generic", [])
