import base64
import hashlib
import json
import logging
import struct
from os import getenv
from pathlib import Path
from re import match
from shutil import unpack_archive
from tempfile import NamedTemporaryFile

import nacl.signing
import redis
import requests
from podman import PodmanClient


def get_redis_client(config):
    return redis.from_url(getenv("REDIS_URL") or config["REDIS_URL"])


def is_modified(config, url: str) -> bool:
    r = get_redis_client(config)

    modified_local = r.hget("last-modified", url)
    if modified_local:
        modified_local = modified_local.decode("utf-8")

    modified_remote = requests.head(url).headers.get("last-modified")

    if modified_local:
        if modified_local == modified_remote:
            return False

    if modified_remote:
        r.hset(
            "last-modified",
            url,
            modified_remote,
        )

    return True


def get_str_hash(string: str, length: int = 32) -> str:
    """Return sha256sum of str with optional length

    Args:
        string (str): input string
        length (int): hash length

    Returns:
        str: hash of string with specified length
    """
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_file_hash(path: str) -> str:
    """Return sha256sum of given path

    Args:
        path (str): path to file

    Returns:
        str: hash of file
    """
    BLOCK_SIZE = 65536

    h = hashlib.sha256()
    with open(path, "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            h.update(fb)
            fb = f.read(BLOCK_SIZE)

    return h.hexdigest()


def get_manifest_hash(manifest: dict) -> str:
    """Return sha256sum of package manifest

    Duplicate packages are automatically removed and the list is sorted to be
    reproducible

    Args:
        manifest(dict): list of packages

    Returns:
        str: hash of `req`
    """
    return get_str_hash(json.dumps(manifest, sort_keys=True))


def get_request_hash(req: dict) -> str:
    """Return sha256sum of an image request

    Creates a reproducible hash of the request by sorting the arguments

    Args:
        req (dict): dict contianing request information

    Returns:
        str: hash of `req`
    """
    return get_str_hash(
        " ".join(
            [
                req.get("distro", ""),
                req.get("version", ""),
                req.get("version_code", ""),
                req.get("target", ""),
                req.get("profile", "").replace(",", "_"),
                get_packages_hash(req.get("packages", "")),
                get_manifest_hash(req.get("packages_versions", {})),
                str(req.get("diff_packages", False)),
                req.get("filesystem", ""),
                get_str_hash(req.get("defaults", "")),
                str(req.get("rootfs_size_mb", "")),
                str(req.get("repository_keys", "")),
                str(req.get("repositories", "")),
            ]
        ),
        32,
    )


def get_packages_hash(packages: list) -> str:
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
        bool: Sucessfull verification

    Todo:
         Currently ignores keynum and pkalg

    """
    pkalg, keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(pub_key))
    sig = base64.b64decode(sig_file.read_text().splitlines()[-1])

    pkalg, keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify(msg_file.read_bytes(), sig)
        return True
    except nacl.exceptions.CryptoError:
        return False


def remove_prefix(text, prefix):
    """Remove prefix from text

    TODO: remove once 3.8 is dropped

    Args:
        text (str): text to remove prefix from
        prefix (str): prefix to remove

    Returns:
        str: text without prefix
    """
    return text[text.startswith(prefix) and len(prefix) :]


def get_container_version_tag(version: str) -> str:
    if match(r"^\d+\.\d+\.\d+$", version):
        logging.debug("Version is a release version")
        version: str = "v" + version
    else:
        logging.info(f"Version {version} is a branch")
        if version == "SNAPSHOT":
            version: str = "master"
        else:
            version: str = "openwrt-" + version.rstrip("-SNAPSHOT")

    return version


def diff_packages(requested_packages: set, default_packages: set):
    """Return a list of packages to install and remove

    Args:
        requested_packages (set): Set of requested packages
        default_packages (set): Set of default packages

    Returns:
        set: Set of packages to install and remove"""
    remove_packages = default_packages - requested_packages
    return requested_packages | set(
        map(lambda p: f"-{p}".replace("--", "-"), remove_packages)
    )


def run_container(podman: PodmanClient, image, command, mounts=[], copy=[]):
    """Run a container and return the returncode, stdout and stderr

    Args:
        podman (PodmanClient): Podman client
        image (str): Image to run
        command (list): Command to run
        mounts (list, optional): List of mounts. Defaults to [].

    Returns:
        tuple: (returncode, stdout, stderr)
    """
    logging.info(f"Running {image} {command} {mounts}")
    container = podman.containers.run(
        image=image,
        command=command,
        detach=True,
        mounts=mounts,
        userns_mode="keep-id",
        cap_drop=["all"],
        no_new_privileges=True,
        privileged=False,
    )

    returncode = container.wait()

    # Podman 4.x changed the way logs are returned
    if podman.version()["Version"].startswith("3"):
        delimiter = b"\n"
    else:
        delimiter = b""

    stdout = delimiter.join(container.logs(stdout=True, stderr=False)).decode("utf-8")
    stderr = delimiter.join(container.logs(stdout=False, stderr=True)).decode("utf-8")

    logging.debug(f"returncode: {returncode}")
    logging.debug(f"stdout: {stdout}")
    logging.debug(f"stderr: {stderr}")

    if copy:
        logging.debug(f"Copying {copy[0]} from container to {copy[1]}")
        container_tar, _ = container.get_archive(copy[0])
        logging.debug(f"Container tar: {container_tar}")

        host_tar = NamedTemporaryFile(delete=True)
        logging.debug(f"Host tar: {host_tar}")

        host_tar.write(b"".join(container_tar))

        logging.debug(f"Copied {container_tar} to {host_tar}")

        unpack_archive(
            host_tar.name,
            copy[1],
            "tar",
        )
        logging.debug(f"Unpacked {host_tar} to {copy[1]}")

        host_tar.close()
        logging.debug(f"Closed {host_tar}")

    container.remove(v=True)

    return returncode, stdout, stderr


def report_error(job, msg):
    logging.warning(f"Error: {msg}")
    job.meta["detail"] = f"Error: {msg}"
    job.save_meta()
    raise


def parse_manifest(manifest_content: str):
    """Parse a manifest file and return a dictionary

    Args:
        manifest (str): Manifest file content

    Returns:
        dict: Dictionary of packages and versions
    """
    return dict(map(lambda pv: pv.split(" - "), manifest_content.splitlines()))


def check_manifest(manifest, packages_versions):
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
