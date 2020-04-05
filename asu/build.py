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


def build(request: dict):
    """Build image request and setup ImageBuilders automatically

    The `request` dict contains properties of the requested image.

    Args:
        request (dict): Contains all properties of requested image
    """

    if "packages" in request:
        assert isinstance(
            request["packages"], set
        ), "packages must be type set not list"
    else:
        request["packages"] = set()

    assert (request["store_path"]).is_dir(), "store_path must be existing directory"

    job = get_current_job()

    log.debug(f"Building {request}")
    cache = (request["cache_path"] / request["version"] / request["target"]).parent
    target, subtarget = request["target"].split("/")
    sums_file = Path(cache / f"{subtarget}_sums")
    sig_file = Path(cache / f"{subtarget}_sums.sig")

    def setup_ib():
        """Setup ImageBuilder based on `request`

        This function downloads and verifies the ImageBuilder archive. Existing
        setups are automatically updated if newer version are available
        upstream.
        """
        log.debug("Setting up ImageBuilder")
        if (cache / subtarget).is_dir():
            rmtree(cache / subtarget)

        download_file("sha256sums.sig", sig_file)
        download_file("sha256sums", sums_file)

        assert verify_usign(
            sig_file, sums_file, request["version_data"]["pubkey"]
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

    def download_file(filename: str, dest: str = None):
        """Download file from upstream target path

        The URL points automatically to the targets folder upstream

        Args:
            filename (str): File in upstream target folder
            dest (str): Optional path to store the file, default to target
                        cache folder
        """
        log.debug(f"Downloading {filename}")
        urllib.request.urlretrieve(
            request["upstream_url"]
            + "/"
            + request["version_data"]["path"]
            + "/targets/"
            + request["target"]
            + "/"
            + filename,
            dest or (cache / filename),
        )

    cache.mkdir(parents=True, exist_ok=True)

    if sig_file.is_file():
        sig_file_headers = urllib.request.urlopen(
            request["upstream_url"]
            + "/"
            + request["version_data"]["path"]
            + "/targets/"
            + request["target"]
            + "/sha256sums.sig"
        ).info()
        log.debug(f"sig_file_headers: \n{sig_file_headers}")
        last_modified = time.mktime(
            time.strptime(
                sig_file_headers.get("Last-Modified"), "%a, %d %b %Y %H:%M:%S %Z"
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

    if request.get("diff_packages", False) and request.get("packages"):
        info_run = subprocess.run(
            ["make", "info"], text=True, capture_output=True, cwd=cache / subtarget
        )
        default_packages = set(
            re.search(r"Default Packages: (.*)\n", info_run.stdout).group(1).split()
        )
        profile_packages = set(
            re.search(
                r"{}:\n    .+\n    Packages: (.+?)\n".format(request["profile"]),
                info_run.stdout,
                re.MULTILINE,
            )
            .group(1)
            .split()
        )
        remove_packages = (default_packages | profile_packages) - request["packages"]
        request["packages"] = request["packages"] | set(
            map(lambda p: f"-{p}", remove_packages)
        )

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

    if manifest_run.returncode:
        log.error(f"Manifest stdout {manifest_run.stdout}")
        log.error(f"Manifest stderr {manifest_run.stderr}")

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

    (request["store_path"] / bin_dir).mkdir(parents=True, exist_ok=True)

    image_build = subprocess.run(
        [
            "make",
            "image",
            f"PROFILE={request['profile']}",
            f"PACKAGES={' '.join(request['packages'])}",
            f"EXTRA_IMAGE_NAME={packages_hash}",
            f"BIN_DIR={request['store_path'] / bin_dir}",
        ],
        text=True,
        capture_output=True,
        cwd=cache / subtarget,
    )

    (request["store_path"] / bin_dir / "buildlog.txt").write_text(
        f"### STDOUT\n\n{image_build.stdout}\n\n### STDERR\n\n{image_build.stderr}"
    )

    # check if running as job or within pytest
    if job:
        job.meta["bin_dir"] = str(bin_dir)
        job.meta["buildlog"] = True
        job.save_meta()

    if image_build.returncode:
        log.error(f"Build stdout {image_build.stdout}")
        log.error(f"Build stderr {image_build.stderr}")

    assert not image_build.returncode, "ImageBuilder failed"

    json_file = Path(request["store_path"] / bin_dir / "profiles.json")

    assert json_file.is_file(), "Image built but no profiles.json file created"

    json_content = json.loads(json_file.read_text())

    assert request["profile"] in json_content["profiles"], "Requested profile not in created profiles.json"

    json_content.update({"manifest": manifest})
    json_content.update(json_content["profiles"][request["profile"]])
    json_content["id"] = request["profile"]
    json_content.pop("profiles")

    return json_content
