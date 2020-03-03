from multiprocessing import Pool
from urllib import request
import json
import re
import urllib.request
import redis

from flask import current_app, Blueprint

bp = Blueprint("janitor", __name__)
r = redis.Redis()


def download_package_indexes(version: str, arch: str = "x86_64"):
    """Download package in index of a version

    This function is used to store all available packages of a version to the
    Redis database. This information is used to validate build requests.

    The `arch` should point tho the architecture supporting the most packages.
    Currently the validation does not distinguishes if a package is available
    for a specific architecture.

    Args:
        version (str): Version to parse
        arch (str): Architecture containing most packages
    """
    version_url = current_app.config["UPSTREAM_URL"] + "/" + version.get("path")
    base_url = f"{version_url}/packages/{arch}"
    sources = ["base", "luci", "packages", "routing", "telephony"]

    packages = []
    for source in sources:
        current_app.logger.info(f"Downloading {source}")
        source_content = (
            urllib.request.urlopen(f"{base_url}/{source}/Packages").read().decode()
        )
        source_packages = re.findall(r"Package: (.+)\n", source_content)
        current_app.logger.info(f"Found {len(source_packages)} packages")
        packages.extend(re.findall(r"Package: (.+)\n", source_content))

    current_app.logger.info(f"Total of {len(packages)} packages found")

    r.sadd(f"packages-{version['name']}", *packages)


def merge_profiles(version: dict, profiles: list, base_url: str):
    profiles_dict = {}
    names_json_overview = {}

    for profile_info in profiles:
        if not profile_info:
            continue

        current_app.logger.info(f"Merging {profile_info['id']}")

        if not names_json_overview:
            names_json_overview = {
                "metadata_version": 1,
                "models": {},
                "target": profile_info["target"],
                "url": f"{base_url}/{{target}}",
                "version_commit": profile_info["version_commit"],
                "version_number": profile_info["version_number"],
            }

        profiles_dict[profile_info["id"]] = profile_info["target"]

        for title in profile_info.get("titles", []):
            name = ""
            if title.get("title"):
                name = title.get("title")
            else:
                vendor = title.get("vendor", "")
                variant = title.get("variant", "")
                name = f"{vendor} {title['model']} {variant}"
            names_json_overview["models"][name.strip()] = {
                "target": profile_info["target"],
                "id": profile_info["id"],
                "images": profile_info["images"],
            }

    r.hmset(f"profiles-{version['name']}", profiles_dict)
    (current_app.config["JSON_PATH"] / f"names-{version['name']}.json").write_text(
        json.dumps(names_json_overview, sort_keys=True, indent="  ")
    )


def download_profile(url: str) -> dict:
    """Download and loads profile JSON

    Args:
        url (str): URL to profile JSON

    Returns:
        dict: Loaded profile JSON
    """
    try:
        return json.load(request.urlopen(url))
    except json.JSONDecodeError:
        current_app.logger.warning(f"Error at {url}")


def get_json_files(version: dict):
    """Download all profile JSON files from server

    This function makes use of the `?json" function of the upstream OpenWrt
    download server which returns a list of all available files. The returned
    list is searched for JSON files and all are downloaded via the
    `download_profile` function.

    All found profiles are stored in the Redis database as a dictionary with
    the target as value. This way it is easy to know the to ImageBuilder
    target required for image creation.

    Args:
        version (str): Version to download
    """
    version_url = current_app.config["UPSTREAM_URL"] + "/" + version.get("path")
    base_url = f"{version_url}/targets"

    files = list(
        map(
            lambda u: f"{base_url}/{u}",
            filter(
                lambda x: x.endswith(".json"),
                json.load(request.urlopen(f"{base_url}/?json")),
            ),
        )
    )

    pool = Pool(20)
    profiles = pool.map(download_profile, files)
    current_app.logger.info("Done downloading profile json files")
    merge_profiles(version, profiles, base_url)


@bp.cli.command("init")
def init():
    """Initialize the data required to run the server

    For this all available packages and profiles for all enabled versions is
    downloaded and stored in the Redis database.
    """
    current_app.logger.info("Init ASU")
    for version in current_app.config["VERSIONS"]["branches"]:
        if not version.get("enabled"):
            current_app.logger.info(f"Skip disabled version {version['name']}")
            continue

        current_app.logger.info(f"Setup {version['name']}")
        get_json_files(version)
        download_package_indexes(version)
