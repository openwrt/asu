import base64
import hashlib
import json
import logging
import struct
from datetime import datetime
from os import getenv
from pathlib import Path
from re import match
from tarfile import TarFile
from tempfile import NamedTemporaryFile

import nacl.signing
import requests
from podman import PodmanClient

import redis

from . import __version__


def get_branch(version):
    if version.endswith("-SNAPSHOT"):
        # e.g. 21.02-snapshot
        return version.rsplit("-", maxsplit=1)[0]
    else:
        # e.g. snapshot, 21.02.0-rc1 or 19.07.7
        return version.rsplit(".", maxsplit=1)[0]


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
                get_packages_hash(req.get("packages", [])),
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


def get_container_version_tag(version: str) -> str:
    if match(r"^\d+\.\d+\.\d+(-rc\d+)?$", version):
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
    return list(
        sorted(
            requested_packages
            | set(map(lambda p: f"-{p}".replace("--", "-"), remove_packages))
        )
    )


def run_container(
    podman: PodmanClient,
    image,
    command,
    mounts=[],
    copy=[],
    user=None,
    environment={},
    working_dir=None,
):
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
        cap_drop=["all"],
        no_new_privileges=True,
        privileged=False,
        user=user,
        working_dir=working_dir,
        environment=environment,
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
        logging.debug(f"Copying {container_tar} to {host_tar}")

        for data in container_tar:
            host_tar.write(data)
        host_tar.flush()

        tar_file = TarFile(host_tar.name)
        tar_file.extractall(copy[1])

        host_tar.close()
        logging.debug(f"Closed {host_tar}")

    try:
        container.remove(v=True)
        podman.volumes.prune()  # TODO: remove once v=True works
    except Exception as e:
        logging.warning(f"Failed to remove container: {e}")

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


def get_targets_upstream(config: dict, version: str) -> list:
    """Return list of targets for a specific version

    Args:
        config (dict): Configuration
        version (str): Version within branch

    Returns:
        list: List of targets
    """
    branch = config["BRANCHES"][get_branch(version)]
    version_path = branch["path"].format(version=version)

    req = requests.get(config["UPSTREAM_URL"] + f"/{version_path}/.targets.json")

    return list(req.json().keys())


def update_targets(config: dict, version) -> list:
    branch = config["BRANCHES"][get_branch(version)]
    version_path = branch["path"].format(version=branch["versions"][0])

    targets = requests.get(
        config["UPSTREAM_URL"] + f"/{version_path}/.targets.json"
    ).json()

    logging.info(f"{branch['name']}: Found {len(targets)} targets")
    pipeline = get_redis_client(config).pipeline(True)
    pipeline.delete(f"targets:{branch['name']}")
    pipeline.hset(f"targets:{branch['name']}", mapping=targets)
    pipeline.execute()

    return targets


def update_profiles(config, version: str, target: str) -> str:
    """Update available profiles of a specific version

    Args:
        config (dict): Configuration
        version(str): Version within branch
        target(str): Target within version
    """
    branch = config["BRANCHES"][get_branch(version)]
    version_path = branch["path"].format(version=version)
    logging.debug(f"{version}/{target}: Update profiles")

    r = get_redis_client(config)

    r.sadd("branches", branch["name"])
    r.sadd(f"versions:{branch['name']}", version)

    profiles_url = (
        config["UPSTREAM_URL"] + f"/{version_path}/targets/{target}/profiles.json"
    )

    req = requests.get(profiles_url)

    if req.status_code != 200:
        logging.warning("Couldn't download %s", profiles_url)
        return False

    metadata = req.json()
    profiles = metadata.pop("profiles", {})
    logging.info(f"{version}/{target}: Found {len(profiles)} profiles")

    r.set(
        f"revision:{version}:{target}",
        metadata["version_code"],
    )
    logging.info(f"{version}/{target}: Found revision {metadata['version_code']}")

    pipeline = r.pipeline(True)
    pipeline.delete(f"profiles:{branch['name']}:{version}:{target}")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            if not r.hexists(f"mapping:{branch['name']}:{version}:{target}", supported):
                logging.info(
                    f"{version}/{target}: Add profile mapping {supported} -> {profile}"
                )
                r.hset(
                    f"mapping:{branch['name']}:{version}:{target}", supported, profile
                )

        pipeline.sadd(f"profiles:{branch['name']}:{version}:{target}", profile)

        profile_path = (
            config["JSON_PATH"] / version_path / "targets" / target / profile
        ).with_suffix(".json")

        profile_path.parent.mkdir(exist_ok=True, parents=True)
        profile_path.write_text(
            json.dumps(
                {
                    **metadata,
                    **data,
                    "id": profile,
                    "build_at": datetime.utcfromtimestamp(
                        int(metadata.get("source_date_epoch", 0))
                    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )

        data["target"] = target

    pipeline.execute()


def update_meta_json(config):
    latest = list(
        map(
            lambda b: b["versions"][0],
            filter(
                lambda b: b.get("enabled"),
                config["BRANCHES"].values(),
            ),
        )
    )

    branches = dict(
        map(
            lambda b: (
                b["name"],
                {
                    **b,
                    "targets": dict(
                        map(
                            lambda a: (a[0].decode(), a[1].decode()),
                            get_redis_client(config)
                            .hgetall(f"targets:{b['name']}")
                            .items(),
                        )
                    ),
                },
            ),
            filter(
                lambda b: b.get("enabled"),
                config["BRANCHES"].values(),
            ),
        )
    )

    config["OVERVIEW"] = {
        "latest": latest,
        "branches": branches,
        "server": {
            "version": __version__,
            "contact": "mail@aparcar.org",
            "allow_defaults": config["ALLOW_DEFAULTS"],
            "repository_allow_list": config["REPOSITORY_ALLOW_LIST"],
        },
    }

    config["JSON_PATH"].mkdir(exist_ok=True, parents=True)

    (config["JSON_PATH"] / "overview.json").write_text(
        json.dumps(config["OVERVIEW"], indent=2, sort_keys=False, default=str)
    )

    (config["JSON_PATH"] / "branches.json").write_text(
        json.dumps(list(branches.values()), indent=2, sort_keys=False, default=str)
    )

    (config["JSON_PATH"] / "latest.json").write_text(json.dumps({"latest": latest}))


def update(config, version: str, target: str):
    update_targets(config, version)
    update_profiles(config, version, target)
    update_meta_json(config)
