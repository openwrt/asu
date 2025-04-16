import base64
import email
import hashlib
import json
import logging
import struct
from os import getgid, getuid
from pathlib import Path
from re import match
from tarfile import TarFile
from tempfile import NamedTemporaryFile
from typing import Optional

import hishel
import nacl.signing
from fastapi import FastAPI
from httpx import Response
from podman import PodmanClient
from podman.domain.containers import Container
from rq import Queue
from rq.job import Job

import redis
from asu.build_request import BuildRequest
from asu.config import settings

log: logging.Logger = logging.getLogger("rq.worker")
log.propagate = False  # Suppress duplicate log messages.


def get_redis_client(unicode: bool = True) -> redis.client.Redis:
    return redis.from_url(settings.redis_url, decode_responses=unicode)


def client_get(url: str, ttl: int = 3600) -> Response:
    return hishel.CacheClient(
        storage=hishel.RedisStorage(client=get_redis_client(False), ttl=ttl),
        controller=hishel.Controller(always_revalidate=True, allow_heuristics=True),
    ).get(url)


def add_timestamp(key: str, labels: dict[str, str] = {}) -> None:
    if not settings.server_stats:
        return
    log.debug(f"Adding timestamp to {key}: {labels}")
    get_redis_client().ts().add(
        key,
        value=1,
        timestamp="*",
        labels=labels,
    )


def get_queue() -> Queue:
    """Return the current queue

    Returns:
        Queue: The current RQ work queue
    """
    return Queue(connection=get_redis_client(False), is_async=settings.async_queue)


def get_branch(version_or_branch: str) -> dict[str, str]:
    if version_or_branch not in settings.branches:
        if version_or_branch.endswith("-SNAPSHOT"):
            # e.g. 21.02-snapshot
            branch_name = version_or_branch.rsplit("-", maxsplit=1)[0]
        else:
            # e.g. snapshot, 21.02.0-rc1 or 19.07.7
            branch_name = version_or_branch.rsplit(".", maxsplit=1)[0]
    else:
        branch_name = version_or_branch

    return {**settings.branches.get(branch_name, {}), "name": branch_name}


def get_str_hash(string: str) -> str:
    """Return sha256sum of str with optional length

    Args:
        string (str): input string

    Returns:
        str: hash of string with specified length
    """
    return hashlib.sha256(bytes(string or "", "utf-8")).hexdigest()


def get_file_hash(path: str) -> str:
    """Return sha256sum of given path

    Args:
        path (str): path to file

    Returns:
        str: hash of file
    """
    BLOCK_SIZE: int = 65536

    h = hashlib.sha256()
    with open(path, "rb") as f:
        fb: bytes = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            h.update(fb)
            fb = f.read(BLOCK_SIZE)

    return h.hexdigest()


def get_manifest_hash(manifest: dict[str, str]) -> str:
    """Return sha256sum of package manifest

    Duplicate packages are automatically removed and the list is sorted to be
    reproducible

    Args:
        manifest(dict): list of packages

    Returns:
        str: hash of `req`
    """
    return get_str_hash(json.dumps(manifest, sort_keys=True))


def get_request_hash(build_request: BuildRequest) -> str:
    """Return sha256sum of an image request

    Creates a reproducible hash of the request by sorting the arguments

    Args:
        req (dict): dict containing request information

    Returns:
        str: hash of `req`
    """
    return get_str_hash(
        "".join(
            [
                build_request.distro,
                build_request.version,
                build_request.version_code,
                build_request.target,
                build_request.profile.replace(",", "_"),
                get_packages_hash(
                    build_request.packages_versions.keys() or build_request.packages
                ),
                get_manifest_hash(build_request.packages_versions),
                str(build_request.diff_packages),
                "",  # build_request.filesystem
                get_str_hash(build_request.defaults),
                str(build_request.rootfs_size_mb),
                str(build_request.repository_keys),
                str(build_request.repositories),
            ]
        ),
    )


def get_packages_hash(packages: list[str]) -> str:
    """Return sha256sum of package list

    Duplicate packages are automatically removed and the list is sorted to be
    reproducible

    Args:
        packages (list): list of packages

    Returns:
        str: hash of `packages`
    """
    return get_str_hash(
        " ".join(
            sorted(
                set(
                    (x.removeprefix("+") for x in packages),
                )
            )
        )
    )


def fingerprint_pubkey_usign(pubkey: str) -> str:
    """Return fingerprint of signify/usign public key

    Args:
        pubkey (str): signify/usign public key

    Returns:
        str: string containing the fingerprint
    """
    keynum = base64.b64decode(pubkey.splitlines()[-1])[2:10]
    return "".join(format(x, "02x") for x in keynum)


def verify_usign(sig_file: Path, msg_file: Path, pub_key: str) -> bool:
    """Verify a signify/usign signature

    This implementation uses pynacl

    Args:
        sig_file (Path): signature file
        msg_file (Path): message file to be verified
        pub_key (str): public key to use for verification

    Returns:
        bool: Successful verification

    Todo:
         Currently ignores keynum and pkalg

    """
    _pkalg, _keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(pub_key))
    sig = base64.b64decode(sig_file.read_text().splitlines()[-1])

    _pkalg, _keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify(msg_file.read_bytes(), sig)
        return True
    except nacl.exceptions.CryptoError:
        return False


def get_container_version_tag(input_version: str) -> str:
    if match(r"^\d+\.\d+\.\d+(-rc\d+)?$", input_version):
        log.debug("Version is a release version")
        version: str = "v" + input_version
    else:
        log.debug(f"Version {input_version} is a branch")
        if input_version == "SNAPSHOT":
            version: str = "master"
        else:
            version: str = "openwrt-" + input_version.removesuffix("-SNAPSHOT")

    return version


def get_podman() -> PodmanClient:
    return PodmanClient(
        base_url=f"unix://{settings.container_socket_path}",
        identity=settings.container_identity,
    )


def diff_packages(
    requested_packages: list[str], default_packages: set[str]
) -> list[str]:
    """Return a list of packages to install and remove

    Args:
        requested_packages (set): List of requested packages in user-specified order
        default_packages (set): Set of default packages

    Returns:
        list: List of packages to install and remove"""
    remove_packages = default_packages - set(requested_packages)
    return (
        sorted(set(map(lambda p: f"-{p}".replace("--", "-"), remove_packages)))
        + requested_packages
    )


def run_cmd(
    container: Container,
    command: list[str],
    copy: list[str] = [],
    environment: dict[str, str] = {},
) -> tuple[int, str, str]:
    returncode, output = container.exec_run(command, demux=True, user="buildbot")

    stdout: str = output[0].decode("utf-8")
    stderr: str = output[1].decode("utf-8")

    log.debug(f"returncode: {returncode}")
    log.debug(f"stdout: {stdout}")
    log.debug(f"stderr: {stderr}")

    if copy:
        log.debug(f"Copying {copy[0]} from container to {copy[1]}")
        container_tar, _ = container.get_archive(copy[0])
        log.debug(f"Container tar: {container_tar}")

        host_tar = NamedTemporaryFile(delete=True)
        log.debug(f"Copying {container_tar} to {host_tar}")

        for data in container_tar:
            host_tar.write(data)
        host_tar.flush()

        with TarFile(host_tar.name) as tar_file:
            for member in tar_file:
                # Fix the owner of the copied files, change to "us".
                member.uid = getuid()
                member.gid = getgid()
                member.mode = 0o755 if member.isdir() else 0o644
            tar_file.extractall(copy[1])
        log.debug(f"Closed {host_tar}")

    return returncode, stdout, stderr


def report_error(job: Job, msg: str) -> None:
    log.warning(f"Error: {msg}")
    job.meta["detail"] = f"Error: {msg}"
    job.meta["imagebuilder_status"] = "failed"
    job.save_meta()
    raise RuntimeError(msg)


def parse_manifest(manifest_content: str) -> dict[str, str]:
    """Parse a manifest file and return a dictionary

    Args:
        manifest (str): Manifest file content

    Returns:
        dict: Dictionary of packages and versions
    """
    if " - " in manifest_content:
        separator = " - "  # OPKG format
    else:
        separator = " "  # APK format

    return dict(map(lambda pv: pv.split(separator), manifest_content.splitlines()))


def check_manifest(
    manifest: dict[str, str], packages_versions: dict[str, str]
) -> Optional[str]:
    """Validate a manifest file

    Args:
        manifest (str): Manifest file content
        packages_versions (dict): Dictionary of packages and versions

    Returns:
        str: Error message or None
    """
    for package, version in packages_versions.items():
        if package not in manifest:
            return f"Impossible package selection: {package} not in manifest"
        if version != manifest[package]:
            return (
                f"Impossible package selection: {package} version not as requested: "
                f"{version} vs. {manifest[package]}"
            )


def parse_packages_file(url: str) -> dict[str, str]:
    res: Response
    if "/snapshots/" in url:  # TODO find better way to check for cutoff
        res = client_get(f"{url}/index.json")
        return res.json() if res.status_code == 200 else {}

    res = client_get(f"{url}/Packages")
    if res.status_code != 200:
        return {}

    index: dict[str, str] = {}
    architecture: str = ""
    parser: email.parser.Parser = email.parser.Parser()
    chunks: list[str] = res.text.strip().split("\n\n")
    for chunk in chunks:
        package: dict[str, str] = parser.parsestr(chunk, headersonly=True)
        if not architecture:
            architecture = package["Architecture"]
        package_name: str = package["Package"]
        if package_abi := package.get("ABIVersion"):
            package_name = package_name.removesuffix(package_abi)

        index[package_name] = package["Version"]

    return {"architecture": architecture, "packages": index}


def parse_feeds_conf(url: str) -> list[str]:
    res: Response = client_get(f"{url}/feeds.conf")
    return (
        [line.split()[1] for line in res.text.splitlines()]
        if res.status_code == 200
        else []
    )


def is_snapshot_build(version: str) -> bool:
    """For imagebuilder containers using 'setup.sh' instead of fully populated."""
    return version.lower().endswith("snapshot")


def is_post_kmod_split_build(path: str) -> bool:
    """Root cause of what's going on here can be found at
    https://github.com/openwrt/buildbot/commit/a75ce026

    The short version is that kmods are no longer in the packages/index.json
    for the versions listed below, so we need to find 'linux_kernel' in the
    profiles.json and do some extra work.

    Versions for which kmods are in 'kmods/<kernel-version>/index.json' and not
    in 'packages/index.json':

      - SNAPSHOT
      - all of 24.10 and later
      - 23.05 builds for 23.05-SNAPSHOT, and 23.05.6 and later
    """

    if path.startswith("snapshots"):
        return True

    version: str = path.split("/")[1]
    if version.startswith("24."):
        return True
    if version.startswith("23."):
        minor_version = version.split(".")[-1]
        if minor_version == "05-SNAPSHOT" or minor_version >= "6":
            return True

    return False


def parse_kernel_version(url: str) -> str:
    """Download a target's profiles.json and return the kernel version string."""
    res: Response = client_get(url)
    if res.status_code != 200:
        return ""

    profiles: dict = res.json()
    kernel_info: dict = profiles.get("linux_kernel")
    if kernel_info:
        kernel_version: str = kernel_info["version"]
        kernel_release: str = kernel_info["release"]
        kernel_vermagic: str = kernel_info["vermagic"]
        return f"{kernel_version}-{kernel_release}-{kernel_vermagic}"
    return ""


def reload_versions(app: FastAPI) -> bool:
    response = client_get(settings.upstream_url + "/.versions.json")

    if response.extensions["from_cache"] and app.versions:
        return False

    versions = response.json()["versions_list"]

    app.versions = [
        version
        for version in versions
        if any(version.startswith(branch) for branch in settings.branches.keys())
    ]

    if response.json()["upcoming_version"]:
        app.versions.append(response.json()["upcoming_version"])

    for branch in settings.branches.keys():
        if branch != "SNAPSHOT":
            app.versions.append(f"{branch}-SNAPSHOT")

    if "SNAPSHOT" in settings.branches.keys():
        app.versions.append("SNAPSHOT")

    app.versions.sort(reverse=True)

    return True


def reload_targets(app: FastAPI, version: str) -> bool:
    branch_data = get_branch(version)
    version_path = branch_data["path"].format(version=version)
    response = client_get(settings.upstream_url + f"/{version_path}/.targets.json")

    if response.extensions["from_cache"] and app.targets[version]:
        return False

    app.targets[version] = response.json()

    return True


def reload_profiles(app: FastAPI, version: str, target: str) -> bool:
    branch_data = get_branch(version)
    version_path = branch_data["path"].format(version=version)
    response = client_get(
        settings.upstream_url + f"/{version_path}/targets/{target}/profiles.json"
    )

    if response.extensions["from_cache"] and app.profiles[version].get(target):
        return False

    app.profiles[version][target] = {
        name: profile
        for profile, data in response.json()["profiles"].items()
        for name in data.get("supported_devices", []) + [profile]
    }

    return True
