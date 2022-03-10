import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from shutil import rmtree

import requests
from rq import get_current_job

from .common import (
    fingerprint_pubkey_usign,
    get_file_hash,
    get_packages_hash,
    verify_usign,
)

log = logging.getLogger("rq.worker")
log.setLevel(logging.DEBUG)


def build(req: dict):
    """Build image request and setup ImageBuilders automatically

    The `request` dict contains properties of the requested image.

    Args:
        request (dict): Contains all properties of requested image
    """

    def report_error(msg):
        log.warning(f"Error: {msg}")
        job.meta["detail"] = f"Error: {msg}"
        job.save_meta()
        raise

    if not req["store_path"].is_dir():
        report_error("Store path missing")

    job = get_current_job()
    job.meta["detail"] = "init"
    job.save_meta()

    log.debug(f"Building {req}")
    cache = (Path.cwd() / "cache" / req["version"] / req["target"]).parent
    target, subtarget = req["target"].split("/")
    sums_file = Path(cache / f"{subtarget}_sums")
    sig_file = Path(cache / f"{subtarget}_sums.sig")

    def setup_ib():
        """Setup ImageBuilder based on `req`

        This function downloads and verifies the ImageBuilder archive. Existing
        setups are automatically updated if newer version are available
        upstream.
        """
        log.debug("Setting up ImageBuilder")
        if (cache / subtarget).is_dir():
            rmtree(cache / subtarget)

        download_file("sha256sums.sig", sig_file)
        download_file("sha256sums", sums_file)

        log.debug("Signatures downloaded" + sig_file.read_text())

        if not verify_usign(sig_file, sums_file, req["branch_data"]["pubkey"]):
            report_error("Bad signature of ImageBuilder archive")

        ib_search = re.search(
            r"^(.{64}) \*(openwrt-imagebuilder-.+?\.Linux-x86_64\.tar\.xz)$",
            sums_file.read_text(),
            re.MULTILINE,
        )

        if not ib_search:
            report_error("Missing Checksum")

        ib_hash, ib_archive = ib_search.groups()

        job.meta["imagebuilder_status"] = "download_imagebuilder"
        job.save_meta()

        download_file(ib_archive)

        if ib_hash != get_file_hash(cache / ib_archive):
            report_error("Bad Checksum")

        (cache / subtarget).mkdir(parents=True, exist_ok=True)

        job.meta["imagebuilder_status"] = "unpack_imagebuilder"
        job.save_meta()

        extract_archive = subprocess.run(
            ["tar", "--strip-components=1", "-xf", ib_archive, "-C", subtarget],
            cwd=cache,
        )

        if extract_archive.returncode:
            report_error("Failed to unpack ImageBuilder archive")

        log.debug(f"Extracted TAR {ib_archive}")

        (cache / ib_archive).unlink()

        for key in req["branch_data"].get("extra_keys", []):
            fingerprint = fingerprint_pubkey_usign(key)
            (cache / subtarget / "keys" / fingerprint).write_text(
                f"untrusted comment: ASU extra key {fingerprint}\n{key}"
            )

        repos_path = cache / subtarget / "repositories.conf"
        repos = repos_path.read_text()

        # speed up downloads with HTTP and (optionally) CDN
        repos = repos.replace("https://downloads.openwrt.org", req["upstream_url"])
        repos = repos.replace("http://downloads.openwrt.org", req["upstream_url"])
        repos = repos.replace("https", "http")

        extra_repos = req["branch_data"].get("extra_repos")
        if extra_repos:
            log.debug("Found extra repos")
            for name, repo in extra_repos.items():
                repos += f"\nsrc/gz {name} {repo}"

        repos_path.write_text(repos)
        log.debug(f"Repos:\n{repos}")

        if (Path.cwd() / "seckey").exists():
            # link key-build to imagebuilder
            (cache / subtarget / "key-build").symlink_to(Path.cwd() / "seckey")
        if (Path.cwd() / "pubkey").exists():
            # link key-build.pub to imagebuilder
            (cache / subtarget / "key-build.pub").symlink_to(Path.cwd() / "pubkey")
        if (Path.cwd() / "newcert").exists():
            # link key-build.ucert to imagebuilder
            (cache / subtarget / "key-build.ucert").symlink_to(Path.cwd() / "newcert")

    def download_file(filename: str, dest: str = None):
        """Download file from upstream target path

        The URL points automatically to the targets folder upstream

        Args:
            filename (str): File in upstream target folder
            dest (str): Optional path to store the file, default to target
                        cache folder
        """
        log.debug(f"Downloading {filename}")
        r = requests.get(
            req["upstream_url"]
            + "/"
            + req["branch_data"]["path"].format(version=req["version"])
            + "/targets/"
            + req["target"]
            + "/"
            + filename
        )

        with open(dest or (cache / filename), "wb") as f:
            f.write(r.content)

    cache.mkdir(parents=True, exist_ok=True)

    stamp_file = cache / f"{subtarget}_stamp"

    sig_file_headers = requests.head(
        req["upstream_url"]
        + "/"
        + req["branch_data"]["path"].format(version=req["version"])
        + "/targets/"
        + req["target"]
        + "/sha256sums.sig"
    ).headers
    log.debug(f"sig_file_headers: \n{sig_file_headers}")

    origin_modified = sig_file_headers.get("last-modified")
    log.info("Origin %s", origin_modified)

    if stamp_file.is_file():
        local_modified = stamp_file.read_text()
        log.info("Local  %s", local_modified)
    else:
        local_modified = ""

    if origin_modified != local_modified:
        log.debug("New ImageBuilder upstream available")
        setup_ib()

    stamp_file.write_text(origin_modified)

    info_run = subprocess.run(
        ["make", "info"], text=True, capture_output=True, cwd=cache / subtarget
    )

    version_code = re.search('Current Revision: "(r.+)"', info_run.stdout).group(1)

    if "version_code" in req:
        if version_code != req.get("version_code"):
            report_error(
                f"Received inncorrect version {version_code} (requested {req['version_code']})"
            )

    if req.get("diff_packages", False):
        default_packages = set(
            re.search(r"Default Packages: (.*)\n", info_run.stdout).group(1).split()
        )
        profile_packages = set(
            re.search(
                r"{}:\n    .+\n    Packages: (.*?)\n".format(req["profile"]),
                info_run.stdout,
                re.MULTILINE,
            )
            .group(1)
            .split()
        )
        remove_packages = (default_packages | profile_packages) - req["packages"]
        req["packages"] = req["packages"] | set(map(lambda p: f"-{p}", remove_packages))

    job.meta["imagebuilder_status"] = "calculate_packages_hash"
    job.save_meta()

    manifest_run = subprocess.run(
        [
            "make",
            "manifest",
            f"PROFILE={req['profile']}",
            f"PACKAGES={' '.join(req.get('packages', ''))}",
            "STRIP_ABI=1",
        ],
        text=True,
        cwd=cache / subtarget,
        capture_output=True,
    )

    if manifest_run.returncode:
        if "Package size mismatch" in manifest_run.stderr:
            rmtree(cache / subtarget)
            return build(req)
        else:
            job.meta["stdout"] = manifest_run.stdout
            job.meta["stderr"] = manifest_run.stderr
            report_error("Impossible package selection")

    manifest = dict(map(lambda pv: pv.split(" - "), manifest_run.stdout.splitlines()))

    for package, version in req.get("packages_versions", {}).items():
        if package not in manifest:
            report_error(f"Impossible package selection: {package} not in manifest")
        if version != manifest[package]:
            report_error(
                f"Impossible package selection: {package} version not as requested: {version} vs. {manifest[package]}"
            )

    manifest_packages = manifest.keys()

    log.debug(f"Manifest Packages: {manifest_packages}")

    packages_hash = get_packages_hash(manifest_packages)
    log.debug(f"Packages Hash {packages_hash}")

    bin_dir = req["request_hash"]

    (req["store_path"] / bin_dir).mkdir(parents=True, exist_ok=True)

    log.debug("Created store path: %s", req["store_path"] / bin_dir)

    build_cmd = [
        "make",
        "image",
        f"PROFILE={req['profile']}",
        f"PACKAGES={' '.join(req.get('packages', []))}",
        f"EXTRA_IMAGE_NAME={packages_hash}",
        f"BIN_DIR={req['store_path'] / bin_dir}",
    ]

    log.debug("Build command: %s", build_cmd)

    job.meta["imagebuilder_status"] = "building_image"
    job.save_meta()

    if req.get("defaults"):
        defaults_file = (
            Path(req["store_path"]) / bin_dir / "files/etc/uci-defaults/99-asu-defaults"
        )
        defaults_file.parent.mkdir(parents=True)
        defaults_file.write_text(req["defaults"])
        build_cmd.append(f"FILES={req['store_path'] / bin_dir / 'files'}")

    log.debug(f"Running {' '.join(build_cmd)}")

    image_build = subprocess.run(
        build_cmd,
        text=True,
        cwd=cache / subtarget,
        capture_output=True,
    )

    job.meta["stdout"] = image_build.stdout
    job.meta["stderr"] = image_build.stderr
    job.meta["build_cmd"] = build_cmd
    job.save_meta()

    if image_build.returncode:
        job.meta["details"] = "image build error"
        job.save_meta()
        return False

    if "is too big" in image_build.stderr:
        report_error("Selected packages exceed device storage")

    json_file = Path(req["store_path"] / bin_dir / "profiles.json")

    if not json_file.is_file():
        report_error("No JSON file found")

    json_content = json.loads(json_file.read_text())

    if req["profile"] not in json_content["profiles"]:
        report_error("Profile not found in JSON file")

    json_content.update({"manifest": manifest})
    json_content.update(json_content["profiles"][req["profile"]])
    json_content["id"] = req["profile"]
    json_content["bin_dir"] = str(bin_dir)
    json_content.pop("profiles")
    json_content["build_at"] = datetime.utcfromtimestamp(
        int(json_content.get("source_date_epoch", 0))
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    json_content["detail"] = "done"

    job.connection.sadd(f"builds-{version_code}-{req['target']}", req["request_hash"])

    job.connection.hincrby(
        "stats-builds",
        "#".join(
            [req["branch_data"]["name"], req["version"], req["target"], req["profile"]]
        ),
    )

    log.debug("JSON content %s", json_content)

    return json_content
