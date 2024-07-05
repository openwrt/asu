import json
import logging
from datetime import datetime

import requests

from asu import __version__
from asu.util import get_branch, get_branch_path, get_redis_client

from .config import settings

log = logging.getLogger("rq.worker")

redis_client = get_redis_client()


def update_targets(version):
    """Update available targets of a specific version

    Args:
        config (dict): Configuration
        version(str): Version within branch
    """
    branch_name = get_branch(version)
    version_path = get_branch_path(branch_name).format(version=version)
    targets = requests.get(settings.upstream_url + f"/{version_path}/.targets.json")

    if targets.status_code != 200:
        log.warning("Couldn't download %s", targets.url)
        return

    targets = targets.json()

    log.info(f"{branch_name}: Found {len(targets)} targets")
    pipeline = redis_client.pipeline(True)
    pipeline.delete(f"targets:{branch_name}")
    pipeline.hset(f"targets:{branch_name}", mapping=targets)
    pipeline.execute()


def update_profiles(version: str, target_subtarget: str) -> str:
    """Update available profiles of a specific version

    Args:
        config (dict): Configuration
        version(str): Version within branch
        target(str): Target within version
    """
    branch_name = get_branch(version)
    version_path = get_branch_path(branch_name).format(version=version)
    log.debug(f"{version}/{target_subtarget}: Update profiles")

    redis_client.sadd("branches", branch_name)
    redis_client.sadd(f"versions:{branch_name}", version)

    profiles_url = (
        settings.upstream_url
        + f"/{version_path}/targets/{target_subtarget}/profiles.json"
    )

    req = requests.get(profiles_url)

    if req.status_code != 200:
        log.warning("Couldn't download %s", profiles_url)
        return False

    metadata = req.json()
    profiles = metadata.pop("profiles", {})
    log.info(f"{version}/{target_subtarget}: Found {len(profiles)} profiles")

    redis_client.set(
        f"revision:{version}:{target_subtarget}",
        metadata["version_code"],
    )
    log.info(f"{version}/{target_subtarget}: Found revision {metadata['version_code']}")

    pipeline = redis_client.pipeline(True)
    pipeline.delete(f"profiles:{branch_name}:{version}:{target_subtarget}")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            if not redis_client.hexists(
                f"mapping:{branch_name}:{version}:{target_subtarget}", supported
            ):
                log.info(
                    f"{version}/{target_subtarget}: Add profile mapping {supported} -> {profile}"
                )
                redis_client.hset(
                    f"mapping:{branch_name}:{version}:{target_subtarget}",
                    supported,
                    profile,
                )

        pipeline.sadd(f"profiles:{branch_name}:{version}:{target_subtarget}", profile)

        profile_path = (
            settings.json_path / version_path / "targets" / target_subtarget / profile
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

        data["target"] = target_subtarget

    pipeline.execute()


def update_meta_json():
    versions_upstream = requests.get(settings.upstream_url + "/.versions.json").json()
    latest = [
        versions_upstream["stable_version"],
        versions_upstream["oldstable_version"],
    ]

    branches = dict(
        map(
            lambda b: (
                b.decode(),
                {
                    "name": b.decode(),
                    "versions": list(redis_client.smembers(f"versions:{b}")),
                    "targets": dict(
                        map(
                            lambda a: (a[0].decode(), a[1].decode()),
                            redis_client.hgetall(f"targets:{b}").items(),
                        )
                    ),
                },
            ),
            redis_client.smembers("branches"),
        )
    )

    overview = {
        "latest": latest,
        "branches": branches,
        "upstream_url": settings.upstream_url,
        "server": {
            "version": __version__,
            "contact": "mail@aparcar.org",
            "allow_defaults": settings.allow_defaults,
            "repository_allow_list": settings.repository_allow_list,
        },
    }

    settings.json_path.mkdir(exist_ok=True, parents=True)

    (settings.json_path / "overview.json").write_text(
        json.dumps(overview, indent=2, sort_keys=False, default=str)
    )

    (settings.json_path / "branches.json").write_text(
        json.dumps(list(branches.values()), indent=2, sort_keys=False, default=str)
    )

    (settings.json_path / "latest.json").write_text(json.dumps({"latest": latest}))


def update(version: str, target_subtarget: str):
    update_targets(version)
    update_profiles(version, target_subtarget)
    update_meta_json()
