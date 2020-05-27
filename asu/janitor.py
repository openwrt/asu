import re
import urllib.request
import requests

from flask import current_app, Blueprint

bp = Blueprint("janitor", __name__)


def get_redis():
    return current_app.config["REDIS_CONN"]


def update_packages(version: dict):
    """Update available packages of a specific target and version
    
    Args:
        version (dict): Containing all version information as defined in VERSIONS
    """
    current_app.logger.info(f"Updating packages of {version['name']}")

    r = get_redis()

    targets = list(map(lambda t: t.decode(), r.smembers(f"targets-{version['name']}")))

    for target in targets:
        current_app.logger.debug(
            f"Update packages of {target} from "
            + current_app.config["JSON_URL"]
            + f"/{target}/index.json"
        )
        req = requests.get(current_app.config["JSON_URL"] + f"/{target}/index.json")
        if req.status_code != 200:
            current_app.logger.warning(f"Could not update packages of {target}")
            continue

        packages = req.json()
        current_app.logger.info(f"{target}: found {len(packages)} packages")
        r.sadd(f"packages-{version['name']}-{target}", *packages)


def update_targets(version: dict):
    """Update available targets of a specific version
    
    Args:
        version (dict): Containing all version information as defined in VERSIONS
    """
    current_app.logger.info(f"Updating targets of {version['name']}")
    r = get_redis()
    req = requests.get(current_app.config["JSON_URL"] + "/targets.json")
    if req.status_code != 200:
        current_app.logger.error(f"Could not download targets.json")
        quit(1)

    targets = req.json()
    current_app.logger.info(f"Found {len(targets)} targets")
    r.sadd(f"targets-{version['name']}", *list(targets.keys()))


def update_profiles(version: dict):
    """Update available profiles of a specific version
    
    Args:
        version (dict): Containing all version information as defined in VERSIONS
    """
    current_app.logger.info(f"Updating profiles of {version['name']}")
    r = get_redis()
    req = requests.get(current_app.config["JSON_URL"] + "/profiles.json")

    if req.status_code != 200:
        current_app.logger.error(f"Could not download profiles.json")
        quit(1)

    profiles = req.json()["profiles"]
    current_app.logger.info(f"Found {len(profiles)} profiles")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            r.hset(f"mapping-{version['name']}", supported, profile)
        r.hset(f"profiles-{version['name']}", profile, data["target"])


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
        update_targets(version)
        update_profiles(version)
        update_packages(version)
