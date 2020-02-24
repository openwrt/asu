import time
import urllib.request
import json
import urllib
from pathlib import Path
import datetime
import re
from shutil import rmtree
import subprocess
import logging

from rq import get_current_job

from .common import get_packages_hash, verify_usign, get_file_hash

log = logging.getLogger("rq.worker")
log.setLevel(logging.DEBUG)


def build(request):
    job = get_current_job()

    log.debug(f"Building {request}")
    cache = (Path("cache") / request["version"] / request["target"]).parent
    target, subtarget = request["target"].split("/")
    sums_file = Path(cache / f"{subtarget}_sums")
    sig_file = Path(cache / f"{subtarget}_sums.sig")

    def setup_ib():
        log.debug("Setting up ImageBuilder")
        if (cache / subtarget).is_dir():
            rmtree(cache / subtarget)

        download_file("sha256sums.sig", sig_file)
        download_file("sha256sums", sums_file)

        assert verify_usign(
            sig_file,
            sums_file,
            request["config"]["VERSIONS"][request["version"]]["pubkey"],
        ), "Bad signature for cheksums"

        # openwrt-imagebuilder-ath79-generic.Linux-x86_64.tar.xz
        ib_search = re.search(
            r"^(.{64}) \*(openwrt-imagebuilder-.+?\.Linux-x86_64\.tar\.xz)$",
            sums_file.read_text(),
            re.MULTILINE,
        )

        assert ib_search, "No ImageBuilder in checksums found"

        ib_hash, ib_archive = ib_search.groups()

        download_file(ib_archive)

        assert ib_hash == get_file_hash(
            cache / ib_archive
        ), "Wrong ImageBuilder archive checksum"

        (cache / subtarget).mkdir(parents=True, exist_ok=True)
        extract_archive = subprocess.run(
            ["tar", "--strip-components=1", "-xf", ib_archive, "-C", subtarget],
            cwd=cache,
        )

        assert not extract_archive.returncode, "Extracting ImageBuilder archive failed"

        log.debug(f"Extracted TAR {ib_archive}")

        (cache / ib_archive).unlink()

    def download_file(filename: str, dest=None):
        log.debug(f"Downloading {filename}")
        urllib.request.urlretrieve(
            request["config"]["UPSTREAM_URL"]
            + "/"
            + request["config"]["VERSIONS"][request["version"]]["path"]
            + "/targets/"
            + request["target"]
            + "/"
            + filename,
            dest or (cache / filename),
        )

    cache.mkdir(parents=True, exist_ok=True)

    if not (request["config"]["STORE_PATH"]).is_dir():
        (request["config"]["STORE_PATH"]).mkdir(parents=True, exist_ok=True)

    if sig_file.is_file():
        last_modified = time.mktime(
            time.strptime(
                urllib.request.urlopen(
                    request["config"]["UPSTREAM_URL"]
                    + "/"
                    + request["config"]["VERSIONS"][request["version"]]["path"]
                    + "/targets/"
                    + request["target"]
                    + "/sha256sums.sig"
                )
                .info()
                .get("Last-Modified"),
                "%a, %d %b %Y %H:%M:%S %Z",
            )
        )
        log.debug(
            "Local  %s", datetime.datetime.fromtimestamp(sig_file.stat().st_mtime)
        )
        log.debug("Remote %s", datetime.datetime.fromtimestamp(last_modified))

        if sig_file.stat().st_mtime < last_modified:
            log.debug("Newer ImageBuilder upstream available")
            setup_ib()
    else:
        setup_ib()

    manifest_run = subprocess.run(
        [
            "make",
            "manifest",
            f"PROFILE={request['profile']}",
            f"PACKAGES={' '.join(request['packages'])}",
        ],
        text=True,
        capture_output=True,
        cwd=cache / subtarget,
    )

    manifest = dict(map(lambda pv: pv.split(" - "), manifest_run.stdout.splitlines()))

    manifest_packages = manifest.keys()

    log.debug(f"Manifest Packages: {manifest_packages}")

    packages_hash = get_packages_hash(manifest_packages)
    log.debug(f"Packages Hash {packages_hash}")

    bin_dir = (
        Path(request["version"])
        / request["target"]
        / request["profile"]
        / packages_hash
    )

    job.meta["bin_dir"] = str(bin_dir)

    if not (request["config"]["STORE_PATH"] / bin_dir).is_dir():
        (request["config"]["STORE_PATH"] / bin_dir).mkdir(parents=True, exist_ok=True)

    image_build = subprocess.run(
        [
            "make",
            "image",
            f"PROFILE={request['profile']}",
            f"PACKAGES={' '.join(request['packages'])}",
            f"EXTRA_IMAGE_NAME={packages_hash}",
            f"BIN_DIR={request['config']['STORE_PATH'] / bin_dir}",
        ],
        text=True,
        capture_output=True,
        cwd=cache / subtarget,
    )

    (request["config"]["STORE_PATH"] / bin_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent="  ")
    )

    (request["config"]["STORE_PATH"] / bin_dir / "buildlog.txt").write_text(
        f"### STDOUT\n\n{image_build.stdout}\n\n### STDERR\n\n{image_build.stderr}"
    )

    job.meta["buildlog"] = True
    job.save_meta()

    assert not image_build.returncode, "ImageBuilder failed"

    json_file = next(
        Path(request["config"]["STORE_PATH"] / bin_dir).glob("openwrt-*.json")
    )

    assert json_file, "Image built but no JSON file created"

    return json_file.name
