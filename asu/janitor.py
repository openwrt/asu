import re
import urllib.request
import requests

from flask import current_app, Blueprint
import email
import json

bp = Blueprint("janitor", __name__)


def get_redis():
    return current_app.config["REDIS_CONN"]


def parse_packages_file(url, repo):
    req = requests.get(url)

    if req.status_code != 200:
        current_app.logger.warning(f"No Packages found at {url}")
        return {}

    packages = {}
    linebuffer = ""
    for line in req.text.splitlines():
        if line == "":
            parser = email.parser.Parser()
            package = parser.parsestr(linebuffer)
            package_name = package.get("Package")
            if package_name:
                packages[package_name] = dict(
                    (name.lower().replace("-", "_"), val)
                    for name, val in package.items()
                )
                packages[package_name]["repository"] = repo
            else:
                print(f"Something wired about {package}")
            linebuffer = ""
        else:
            linebuffer += line + "\n"

    current_app.logger.debug(f"Found {len(packages)} in {repo}")

    return packages


def get_targets(version):
    json_url = current_app.config["UPSTREAM_URL"]
    req = requests.get(f"{json_url}/{version['path']}/targets/?json-targets")
    if req.status_code != 200:
        current_app.logger.warning(f"No targets.json found for {version['name']}")
        return []

    return req.json()


def get_packages_target_base(version, target):
    return parse_packages_file(
        current_app.config["UPSTREAM_URL"]
        + "/"
        + version["path"]
        + f"/targets/{target}/packages/Packages.manifest",
        target,
    )


def get_packages_arch_repo(version, arch, repo):
    return parse_packages_file(
        current_app.config["UPSTREAM_URL"]
        + "/"
        + version["path"]
        + f"/packages/{arch}/{repo}/Packages.manifest",
        repo,
    )


def update_version(version):
    r = get_redis()

    profiles = {"profiles": {}}

    targets = list(
        filter(
            lambda p: not p.startswith("scheduled_for_removal"), get_targets(version)
        )
    )
    current_app.logger.info(f"Found {len(targets)} targets")

    r.sadd(f"targets-{version['name']}", *targets)

    for target in targets:
        update_target_packages(version, target)
        metadata, profiles_target = update_target_profiles(version, target)
        profiles.update(metadata)
        profiles["profiles"].update(profiles_target)

        profiles.pop("target", None)

    profiles_path = current_app.config["JSON_PATH"] / version["path"] / "profiles.json"
    profiles_path.parent.mkdir(exist_ok=True, parents=True)

    profiles_path.write_text(
        json.dumps(profiles, sort_keys=True, separators=(",", ":"))
    )

    overview_path = current_app.config["JSON_PATH"] / version["path"] / "overview.json"
    overview = {
        "metadata_version": 1,
        "version_code": profiles["version_code"],
        "version_number": profiles["version_number"],
        "profiles": {},
    }
    for profile, data in profiles["profiles"].items():
        overview["profiles"][profile] = {
            "titles": data["titles"],
            "target": data["target"],
        }
    overview_path.write_text(
        json.dumps(overview, sort_keys=True, separators=(",", ":"))
    )


def update_target_packages(version: dict, target: str):
    current_app.logger.info(f"Updating packages of {version['name']}")
    r = get_redis()

    packages = get_packages_target_base(version, target)

    if not "base-files" in packages:
        current_app.logger.warning(f"{target}: missing base-files package")
        return

    arch = packages["base-files"]["architecture"]

    for repo in ["base", "packages", "luci", "routing", "telephony", "freifunk"]:
        packages.update(get_packages_arch_repo(version, arch, repo))

    for name, url in version.get("extra_repos", {}).items():
        current_app.logger.debug(f"Update extra repo {name} at {url}")
        packages.update(parse_packages_file(f"{url}/Packages", name))

    output_path = current_app.config["JSON_PATH"] / version["path"] / target
    output_path.mkdir(exist_ok=True, parents=True)

    (output_path / "manifest.json").write_text(
        json.dumps(packages, sort_keys=True, separators=(",", ":"))
    )

    package_index = list(packages.keys())

    (output_path / "index.json").write_text(
        json.dumps(package_index, sort_keys=True, separators=(",", ":"))
    )

    current_app.logger.info(f"{target}: found {len(package_index)} packages")
    r.sadd(f"packages-{version['name']}-{target}", *package_index)


def update_target_profiles(version: dict, target: str):
    """Update available profiles of a specific version

    Args:
        version (dict): Containing all version information as defined in VERSIONS
    """
    current_app.logger.info(f"Updating profiles of {version['name']}/{target}")
    r = get_redis()
    req = requests.get(
        current_app.config["UPSTREAM_URL"]
        + f"/{version['path']}/targets/{target}/profiles.json"
    )

    if req.status_code != 200:
        current_app.logger.warning(f"Could not download profiles.json for {target}")
        return {}, {}

    metadata = req.json()
    profiles = metadata.pop("profiles", {})

    current_app.logger.info(f"Found {len(profiles)} profiles")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            r.hset(f"mapping-{version['name']}", supported, profile)
        r.hset(f"profiles-{version['name']}", profile, target)
        profile_path = (
            current_app.config["JSON_PATH"] / version["path"] / target / profile
        ).with_suffix(".json")
        profile_path.parent.mkdir(exist_ok=True, parents=True)
        profile_path.write_text(
            json.dumps({**data, **metadata}, sort_keys=True, separators=(",", ":"))
        )

        data["target"] = target

    return metadata, profiles


@bp.cli.command("update")
def update():
    """Update the data required to run the server

    For this all available packages and profiles for all enabled versions is
    downloaded and stored in the Redis database.
    """
    current_app.logger.info("Init ASU")

    for version in current_app.config["VERSIONS"]["branches"]:
        if not version.get("enabled"):
            current_app.logger.info(f"Skip disabled version {version['name']}")
            continue

        current_app.logger.info(f"Update {version['name']}")
        update_version(version)
