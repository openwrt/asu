"""
Update the version/target database with all the specified versions, targets
and subtargets.  By setting appropriate values in the `version_filter`
dictionary, you can limit the collection of data stored.  This is useful when
running a local server where you are only interested in supporting a small
subset of the full OpenWrt builds available.

By default, `version_filter` is set to `None`, resulting in all available
data being updated.
"""

import sys
from requests import Session
from asu.config import settings
from asu.util import get_redis_client

session = Session()

port = "8000"  # Somehow extract from podman-compose.yml?
asu_url = f"http://localhost:{port}"
token = settings.update_token
upstream = settings.upstream_url

extra_versions = ["22.03-SNAPSHOT", "23.05-SNAPSHOT"]

# Example version filtering: set to your desired versions and targets.
# Set `version_filter = None` to reload all versions, targets and subtargets.
version_filter = {
    "21.02.0": {"x86/64"},
    "21.02.1": {"x86/64"},
    "21.02.2": {"x86/64"},
    "21.02.3": {"x86/64"},
    "21.02.4": {"x86/64"},
    "21.02.5": {"x86/64"},
    "21.02.6": {"x86/64"},
    "21.02.7": {"x86/64"},
    "22.03.0": {"x86/64"},
    "22.03.1": {"x86/64"},
    "22.03.2": {"x86/64"},
    "22.03.3": {"x86/64"},
    "22.03.4": {"x86/64"},
    "22.03.5": {"x86/64"},
    "22.03.6": {"x86/64"},
    "22.03.7": {"x86/64"},
    "22.03-SNAPSHOT": {"x86/64"},
    "23.05.0": {"x86/64"},
    "23.05.2": {"x86/64"},
    "23.05.3": {"x86/64"},
    "23.05.4": {"x86/64"},
    "23.05.5": {
        "ath79/generic",
        "x86/64",
    },
    "23.05-SNAPSHOT": {"x86/64"},
    "SNAPSHOT": {
        "ath79/generic",
        "bcm27xx/bcm2708",
        "bcm53xx/generic",
        "mediatek/mt7622",
        "mvebu/cortexa72",
        "tegra/generic",
        "x86/64",
        "x86/generic",
        "x86/geode",
        "x86/legacy",
    },
}
version_filter = None  # Delete this line to use above filters.


def skip_version(version):
    return version_filter and version not in version_filter


def targets_from_version(version):
    return version_filter.get(version, None) if version_filter else None


def skip_target(target, filter):
    return filter and target not in filter


def reload_all():
    versions = session.get(f"{upstream}/.versions.json").json()["versions_list"]
    versions.extend(extra_versions)
    for version in sorted(set(versions)):
        if skip_version(version):
            continue

        print(f"Reloading {version}")
        targets = session.get(f"{upstream}/releases/{version}/.targets.json")
        if targets.status_code == 404:
            print(f"Targets not found for {version}")
            continue

        targets = targets.json()
        target_filter = targets_from_version(version)
        for target in targets:
            if skip_target(target, target_filter):
                continue
            print(f"Reloading {version}/{target}")
            session.get(
                f"{asu_url}/api/v1/update/{version}/{target}",
                headers={"X-Update-Token": token},
            )

    if not skip_version("SNAPSHOT"):
        targets = session.get(f"{upstream}/snapshots/.targets.json").json()
        target_filter = targets_from_version("SNAPSHOT")
        for target in targets:
            if skip_target(target, target_filter):
                continue
            print(f"Reloading SNAPSHOT/{target}")
            session.get(
                f"{asu_url}/api/v1/update/SNAPSHOT/{target}",
                headers={"X-Update-Token": token},
            )


# "Flushing" wipes the whole redis database, including build status.
# Run misc/cleaner.py after if you wish to delete the unused entries
# in public/store/.
flush = "--flush" in sys.argv

redis_client = get_redis_client()
if flush:
    print("Flushing:", redis_client.flushall())
reload_all()
print("Redis keys:", redis_client.keys()[:20])
