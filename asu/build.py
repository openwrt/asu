import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from shutil import copyfile, rmtree

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
    target, subtarget = req["target"].split("/")
    cache = req.get("cache_path", Path.cwd()) / "cache" / req["version"]
    cache_workdir = cache / target / subtarget
    sums_file = Path(cache / target / f"{subtarget}_sums")
    sig_file = Path(cache / target / f"{subtarget}_sums.sig")

    def setup_ib():
        """Setup ImageBuilder based on `req`

        This function downloads and verifies the ImageBuilder archive. Existing
        setups are automatically updated if newer version are available
        upstream.
        """
        log.debug("Setting up ImageBuilder")
        if (cache_workdir).is_dir():
            rmtree(cache_workdir)

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

        if ib_hash != get_file_hash(cache / target / ib_archive):
            report_error("Bad Checksum")

        (cache_workdir).mkdir(parents=True, exist_ok=True)

        job.meta["imagebuilder_status"] = "unpack_imagebuilder"
        job.save_meta()

        extract_archive = subprocess.run(
            ["tar", "--strip-components=1", "-xf", ib_archive, "-C", subtarget],
            cwd=cache / target,
        )

        if extract_archive.returncode:
            report_error("Failed to unpack ImageBuilder archive")

        log.debug(f"Extracted TAR {ib_archive}")

        (cache / target / ib_archive).unlink()

        for key in req["branch_data"].get("extra_keys", []):
            fingerprint = fingerprint_pubkey_usign(key)
            (cache_workdir / "keys" / fingerprint).write_text(
                f"untrusted comment: ASU extra key {fingerprint}\n{key}"
            )

        repos_path = cache_workdir / "repositories.conf"
        repos = repos_path.read_text()

        extra_repos = req["branch_data"].get("extra_repos")
        if extra_repos:
            log.debug("Found extra repos")
            for name, repo in extra_repos.items():
                repos += f"\nsrc/gz {name} {repo}"

        repos_path.write_text(repos)
        log.debug(f"Repos:\n{repos}")

        if (Path.cwd() / "seckey").exists():
            # link key-build to imagebuilder
            (cache_workdir / "key-build").symlink_to(Path.cwd() / "seckey")
        if (Path.cwd() / "pubkey").exists():
            # link key-build.pub to imagebuilder
            (cache_workdir / "key-build.pub").symlink_to(Path.cwd() / "pubkey")
        if (Path.cwd() / "newcert").exists():
            # link key-build.ucert to imagebuilder
            (cache_workdir / "key-build.ucert").symlink_to(Path.cwd() / "newcert")

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

        with open(dest or (cache / target / filename), "wb") as f:
            f.write(r.content)

    (cache / target).mkdir(parents=True, exist_ok=True)

    stamp_file = cache / target / f"{subtarget}_stamp"

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

    if not (cache_workdir / ".config.orig").exists():
        # backup original configuration to keep default filesystems
        copyfile(
            cache_workdir / ".config",
            cache_workdir / ".config.orig",
        )

    stamp_file.write_text(origin_modified)

    info_run = subprocess.run(
        ["make", "info"], text=True, capture_output=True, cwd=cache_workdir
    )

    version_code = re.search('Current Revision: "(r.+)"', info_run.stdout).group(1)

    if "version_code" in req:
        if version_code != req.get("version_code"):
            report_error(
                f"Received inncorrect version {version_code} (requested {req['version_code']})"
            )

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

    if req.get("diff_packages", False):
        remove_packages = (default_packages | profile_packages) - req["packages"]
        req["packages"] = req["packages"] | set(map(lambda p: f"-{p}", remove_packages))

    job.meta["imagebuilder_status"] = "calculate_packages_hash"
    job.save_meta()

    manifest_run = subprocess.run(
        [
            "make",
            "manifest",
            f"PROFILE={req['profile']}",
            f"PACKAGES={' '.join(sorted(req.get('packages', [])))}",
            "STRIP_ABI=1",
        ],
        text=True,
        cwd=cache_workdir,
        capture_output=True,
    )

    if manifest_run.returncode:
        if "Package size mismatch" in manifest_run.stderr:
            rmtree(cache_workdir)
            return build(req)
        else:
            job.meta["stdout"] = manifest_run.stdout
            job.meta["stderr"] = manifest_run.stderr
            print(manifest_run.stdout)
            print(manifest_run.stderr)
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

    if "filesystem" in req:
        config_path = cache_workdir / ".config"
        config = config_path.read_text()

        for filesystem in ["squashfs", "ext4fs", "ubifs", "jffs2"]:
            # this implementation uses `startswith` since a running device thinks
            # it's running `ext4` while really there is `ext4fs` running
            if not filesystem.startswith(req.get("filesystem", filesystem)):
                log.debug(f"Disable {filesystem}")
                config = config.replace(
                    f"CONFIG_TARGET_ROOTFS_{filesystem.upper()}=y",
                    f"# CONFIG_TARGET_ROOTFS_{filesystem.upper()} is not set",
                )
            else:
                log.debug(f"Enable {filesystem}")
                config = config.replace(
                    f"# CONFIG_TARGET_ROOTFS_{filesystem.upper()} is not set",
                    f"CONFIG_TARGET_ROOTFS_{filesystem.upper()}=y",
                )

        config_path.write_text(config)
    else:
        copyfile(
            cache_workdir / ".config.orig",
            cache_workdir / ".config",
        )

    build_cmd = [
        "make",
        "image",
        f"PROFILE={req['profile']}",
        f"PACKAGES={' '.join(sorted(req.get('packages', [])))}",
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
        cwd=cache_workdir,
        capture_output=True,
    )

    job.meta["stdout"] = image_build.stdout
    job.meta["stderr"] = image_build.stderr
    job.meta["build_cmd"] = build_cmd
    job.save_meta()

    if image_build.returncode:
        report_error("Error while building firmware. See stdout/stderr")

    if "is too big" in image_build.stderr:
        report_error("Selected packages exceed device storage")

    json_file = Path(req["store_path"] / bin_dir / "profiles.json")

    if not json_file.is_file():
        report_error("No JSON file found")

    json_content = json.loads(json_file.read_text())

    if req["profile"] not in json_content["profiles"]:
        report_error("Profile not found in JSON file")

    now_timestamp = int(datetime.now().timestamp())

    json_content.update({"manifest": manifest})
    json_content.update(json_content["profiles"][req["profile"]])
    json_content["id"] = req["profile"]
    json_content["bin_dir"] = str(bin_dir)
    json_content.pop("profiles")
    json_content["build_at"] = datetime.utcfromtimestamp(
        int(json_content.get("source_date_epoch", 0))
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    json_content["detail"] = "done"

    log.debug("JSON content %s", json_content)

    job.connection.sadd(f"builds:{version_code}:{req['target']}", req["request_hash"])

    job.connection.hincrby(
        "stats:builds",
        "#".join(
            [req["branch_data"]["name"], req["version"], req["target"], req["profile"]]
        ),
    )

    # Set last build timestamp for current target/subtarget to now
    job.connection.hset(
        f"worker:{job.worker_name}:last_build", req["target"], now_timestamp
    )

    # Iterate over all targets/subtargets of the worker and remove the once inactive for a week
    for target_subtarget, last_build_timestamp in job.connection.hgetall(
        f"worker:{job.worker_name}:last_build"
    ).items():
        target_subtarget = target_subtarget.decode()

        log.debug("now_timestamp        %s %s", target_subtarget, now_timestamp)
        log.debug(
            "last_build_timestamp %s %s",
            target_subtarget,
            last_build_timestamp.decode(),
        )

        if now_timestamp - int(last_build_timestamp.decode()) > 60 * 60 * 24 * 7:
            log.info("Removing unused ImageBuilder for %s", target_subtarget)
            job.connection.hdel(
                f"worker:{job.worker_name}:last_build", target_subtarget
            )
            if (cache / target_subtarget).exists():
                rmtree(cache / target_subtarget)
        else:
            log.debug("Keeping ImageBuilder for %s", target_subtarget)

    return json_content
