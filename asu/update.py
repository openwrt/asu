import json
import logging
from datetime import datetime

import requests

from . import __version__
from .common import get_branch, get_redis_client

log = logging.getLogger("rq.worker")


def update_targets(config: dict, version):
    """Update available targets of a specific version

    Args:
        config (dict): Configuration
        version(str): Version within branch
    """
    branch = config["BRANCHES"][get_branch(version)]
    version_path = branch["path"].format(version=branch["versions"][0])

    targets = requests.get(config["UPSTREAM_URL"] + f"/{version_path}/.targets.json")

    if targets.status_code != 200:
        log.warning("Couldn't download %s", targets.url)
        return

    targets = targets.json()

    log.info(f"{branch['name']}: Found {len(targets)} targets")
    pipeline = get_redis_client(config).pipeline(True)
    pipeline.delete(f"targets:{branch['name']}")
    pipeline.hset(f"targets:{branch['name']}", mapping=targets)
    pipeline.execute()


def update_profiles(config, version: str, target_subtarget: str) -> str:
    """Update available profiles of a specific version

    Args:
        config (dict): Configuration
        version(str): Version within branch
        target(str): Target within version
    """
    branch = config["BRANCHES"][get_branch(version)]
    version_path = branch["path"].format(version=version)
    log.debug(f"{version}/{target_subtarget}: Update profiles")

    r = get_redis_client(config)

    r.sadd("branches", branch["name"])
    r.sadd(f"versions:{branch['name']}", version)

    profiles_url = (
        config["UPSTREAM_URL"]
        + f"/{version_path}/targets/{target_subtarget}/profiles.json"
    )

    req = requests.get(profiles_url)

    if req.status_code != 200:
        log.warning("Couldn't download %s", profiles_url)
        return False

    metadata = req.json()
    profiles = metadata.pop("profiles", {})
    log.info(f"{version}/{target_subtarget}: Found {len(profiles)} profiles")

    r.set(
        f"revision:{version}:{target_subtarget}",
        metadata["version_code"],
    )
    log.info(f"{version}/{target_subtarget}: Found revision {metadata['version_code']}")

    pipeline = r.pipeline(True)
    pipeline.delete(f"profiles:{branch['name']}:{version}:{target_subtarget}")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            if not r.hexists(
                f"mapping:{branch['name']}:{version}:{target_subtarget}", supported
            ):
                log.info(
                    f"{version}/{target_subtarget}: Add profile mapping {supported} -> {profile}"
                )
                r.hset(
                    f"mapping:{branch['name']}:{version}:{target_subtarget}",
                    supported,
                    profile,
                )

        pipeline.sadd(
            f"profiles:{branch['name']}:{version}:{target_subtarget}", profile
        )

        profile_path = (
            config["JSON_PATH"] / version_path / "targets" / target_subtarget / profile
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


def update(config, version: str, target_subtarget: str):
    update_targets(config, version)
    update_profiles(config, version, target_subtarget)
    update_meta_json(config)
