import base64
import email
import hashlib
import json
import logging
import struct
from os import getuid, getgid
from pathlib import Path
from re import match
from tarfile import TarFile
from tempfile import NamedTemporaryFile
from typing import Optional

import httpx
import nacl.signing
from podman import PodmanClient
from podman.domain.containers import Container
from rq import Queue
from rq.job import Job

import redis
from asu.build_request import BuildRequest
from asu.config import settings


REQUEST_HASH_LENGTH: int = 32

log: logging.Logger = logging.getLogger("rq.worker")
log.propagate = False  # Suppress duplicate log messages.


def get_redis_client(unicode: bool = True) -> redis.client.Redis:
    return redis.from_url(settings.redis_url, decode_responses=unicode)


def add_timestamp(key: str, labels: dict[str, str] = {}) -> None:
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


def get_str_hash(string: str, length: int = REQUEST_HASH_LENGTH) -> str:
    """Return sha256sum of str with optional length

    Args:
        string (str): input string
        length (int): hash length

    Returns:
        str: hash of string with specified length
    """
    h = hashlib.sha256(bytes(string or "", "utf-8"))
    return h.hexdigest()[:length]


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
                get_packages_hash(build_request.packages),
                get_manifest_hash(build_request.packages_versions),
                str(build_request.diff_packages),
                "",  # build_request.filesystem
                get_str_hash(build_request.defaults),
                str(build_request.rootfs_size_mb),
                str(build_request.repository_keys),
                str(build_request.repositories),
            ]
        ),
        REQUEST_HASH_LENGTH,
    )


def get_packages_hash(packages: list[str]) -> str:
    """Return sha256sum of package list

    Duplicate packages are automatically removed and the list is sorted to be
    reproducible

    Args:
        packages (list): list of packages

    Returns:
        str: hash of `req`
    """
    return get_str_hash(" ".join(sorted(list(set(packages)))), 12)


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
        base_url=settings.container_host,
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
    return dict(map(lambda pv: pv.split(" - "), manifest_content.splitlines()))


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
    res: httpx.Response
    if "/snapshots/" in url:
        res = httpx.get(f"{url}/index.json")
        return res.json() if res.status_code == 200 else {}

    res = httpx.get(f"{url}/Packages")
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
    res: httpx.Response = httpx.get(f"{url}/feeds.conf")
    return (
        [line.split()[1] for line in res.text.splitlines()]
        if res.status_code == 200
        else []
    )
