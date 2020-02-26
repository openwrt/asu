from multiprocessing import Pool
from urllib import request
import json
import re
import urllib.request

import click
from flask import current_app, Blueprint

from .common import cwd

bp = Blueprint("janitor", __name__)


def pretty_json_dump(filename, data):
    (cwd() / filename).write_text(json.dumps(data, sort_keys=True, indent="  "))


def download_package_indexes(version):
    version_url = (
        current_app.config["UPSTREAM_URL"]
        + "/"
        + current_app.config["VERSIONS"][version].get("path")
    )
    base_url = f"{version_url}/packages/x86_64"
    sources = ["base", "luci", "packages", "routing", "telephony"]

    packages = set()
    for source in sources:
        current_app.logger.info(f"Downloading {source}")
        source_content = (
            urllib.request.urlopen(f"{base_url}/{source}/Packages").read().decode()
        )
        source_packages = set(re.findall(r"Package: (.+)\n", source_content))
        current_app.logger.info(f"Found {len(source_packages)} packages")
        packages.update(re.findall(r"Package: (.+)\n", source_content))

    current_app.logger.info(f"Total of {len(packages)} packages found")

    pretty_json_dump(f"public/packages-{version}.json", sorted(list(packages)))


def fill_metadata(dictionary, profile_info, base_url):
    dictionary.update(
        {
            "metadata_version": 1,
            "target": profile_info["target"],
            "version_commit": profile_info["version_commit"],
            "version_number": profile_info["version_number"],
            "url": f"{base_url}/{{target}}",
        }
    )


def merge_profiles(profiles, base_url):
    profiles_json_overview = {}
    names_json_overview = {}
    version = "unknown"

    for profile_info in profiles:
        if not profile_info:
            continue

        current_app.logger.info(f"Merging {profile_info['id']}")

        if not profiles_json_overview:
            fill_metadata(profiles_json_overview, profile_info, base_url)
            fill_metadata(names_json_overview, profile_info, base_url)
            profiles_json_overview["profiles"] = {}
            names_json_overview["models"] = {}
            version = profile_info["version_number"]

        profiles_json_overview["profiles"][profile_info["id"]] = {
            "target": profile_info["target"]
        }

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

    pretty_json_dump(f"public/profiles-{version}.json", profiles_json_overview)
    pretty_json_dump(f"public/names-{version}.json", names_json_overview)


def download_profile(url):
    try:
        return json.load(request.urlopen(url))
    except json.JSONDecodeError:
        current_app.logger.warning(f"Error at {url}")


def get_json_files(version):
    version_url = (
        current_app.config["UPSTREAM_URL"]
        + "/"
        + current_app.config["VERSIONS"][version].get("path")
    )
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
    merge_profiles(profiles, base_url)


@bp.cli.command("init")
def init():
    current_app.logger.info("Init ASU")
    for current_version in current_app.config["VERSIONS"].keys():
        current_app.logger.info(f"Setup {current_version}")
        get_json_files(current_version)
        download_package_indexes(current_version)
