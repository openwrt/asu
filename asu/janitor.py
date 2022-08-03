import email
import json
from datetime import datetime
from shutil import rmtree
from time import sleep

import click
import requests
from flask import Blueprint, current_app
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.registry import FinishedJobRegistry

from asu import __version__
from asu.common import get_redis, is_modified

bp = Blueprint("janitor", __name__)


def update_set(key: str, *data: list):
    pipeline = get_redis().pipeline(True)
    pipeline.delete(key)
    pipeline.sadd(key, *data)
    pipeline.execute()


def parse_packages_file(url, repo):
    r = get_redis()
    req = requests.get(url)

    if req.status_code != 200:
        current_app.logger.warning(f"No Packages found at {url}")
        return {}

    packages = {}
    mapping = {}
    linebuffer = ""
    for line in req.text.splitlines():
        if line == "":
            parser = email.parser.Parser()
            package = parser.parsestr(linebuffer)
            source_name = package.get("SourceName")
            if source_name:
                packages[source_name] = dict(
                    (name.lower().replace("-", "_"), val)
                    for name, val in package.items()
                )
                packages[source_name]["repository"] = repo
                package_name = package.get("Package")
                if source_name != package_name:
                    mapping[package_name] = source_name
            else:
                current_app.logger.warning(f"Something weird about {package}")
            linebuffer = ""
        else:
            linebuffer += line + "\n"

    for package, source in mapping.items():
        if not r.hexists("mapping-abi", package):
            current_app.logger.info(f"{repo}: Add ABI mapping {package} -> {source}")
            r.hset("mapping-abi", package, source)

    return packages


def get_packages_target_base(branch, version, target):
    version_path = branch["path"].format(version=version)
    return parse_packages_file(
        current_app.config["UPSTREAM_URL"]
        + "/"
        + version_path
        + f"/targets/{target}/packages/Packages.manifest",
        target,
    )


def get_packages_arch_repo(branch, arch, repo):
    version_path = branch["path"].format(version=branch["versions"][0])
    # https://mirror-01.infra.openwrt.org/snapshots/packages/aarch64_cortex-a53/base/
    return parse_packages_file(
        current_app.config["UPSTREAM_URL"]
        + "/"
        + version_path
        + f"/packages/{arch}/{repo}/Packages.manifest",
        repo,
    )


def update_branch(branch):
    version_path = branch["path"].format(version=branch["versions"][0])
    targets = list(
        filter(
            lambda t: not t.startswith("."),
            requests.get(
                current_app.config["UPSTREAM_URL"]
                + f"/{version_path}/targets?json-targets"
            ).json(),
        )
    )

    if not targets:
        current_app.logger.warning("No targets found for {branch['name']}")
        return

    update_set(f"targets:{branch['name']}", *list(targets))

    packages_path = branch["path_packages"].format(branch=branch["name"])
    packages_path = branch["path_packages"].format(branch=branch["name"])
    output_path = current_app.config["JSON_PATH"] / packages_path
    output_path.mkdir(exist_ok=True, parents=True)

    architectures = set()

    for version in branch["versions"]:
        current_app.logger.info(f"Update {branch['name']}/{version}")
        # TODO: ugly
        version_path = branch["path"].format(version=version)
        version_path_abs = current_app.config["JSON_PATH"] / version_path
        output_path = current_app.config["JSON_PATH"] / packages_path
        version_path_abs.mkdir(exist_ok=True, parents=True)
        packages_symlink = version_path_abs / "packages"

        if not packages_symlink.exists():
            packages_symlink.symlink_to(output_path)

        for target in targets:
            update_target_packages(branch, version, target)

        for target in targets:
            if target_arch := update_target_profiles(branch, version, target):
                architectures.add(target_arch)

        overview = {
            "branch": branch["name"],
            "release": version,
            "image_url": current_app.config["UPSTREAM_URL"]
            + f"/{version_path}/targets/{{target}}",
            "profiles": [],
        }

        for profile_file in (version_path_abs / "targets").rglob("**/*.json"):
            if profile_file.stem in ["index", "manifest", "overview"]:
                continue
            profile = json.loads(profile_file.read_text())
            overview["profiles"].append(
                {
                    "id": profile_file.stem,
                    "target": profile["target"],
                    "titles": profile["titles"],
                }
            )
        (version_path_abs / "overview.json").write_text(
            json.dumps(overview, sort_keys=True, separators=(",", ":"))
        )

    for architecture in architectures:
        update_arch_packages(branch, architecture)


def update_target_packages(branch: dict, version: str, target: str):
    current_app.logger.info(f"{version}/{target}: Update packages")

    version_path = branch["path"].format(version=version)
    r = get_redis()

    if not is_modified(
        current_app.config["UPSTREAM_URL"]
        + "/"
        + version_path
        + f"/targets/{target}/packages/Packages.manifest"
    ):
        current_app.logger.debug(f"{version}/{target}: Skip package update")
        return

    packages = get_packages_target_base(branch, version, target)

    if len(packages) == 0:
        current_app.logger.warning(f"No packages found for {target}")
        return

    current_app.logger.debug(f"{version}/{target}: Found {len(packages)}")

    update_set(f"packages:{branch['name']}:{version}:{target}", *list(packages.keys()))

    virtual_packages = {
        vpkg.split("=")[0]
        for pkg in packages.values()
        if (provides := pkg.get("provides"))
        for vpkg in provides.split(", ")
    }
    r.sadd(
        f"packages:{branch['name']}:{version}:{target}",
        *(virtual_packages | packages.keys()),
    )

    output_path = current_app.config["JSON_PATH"] / version_path / "targets" / target
    output_path.mkdir(exist_ok=True, parents=True)

    (output_path / "manifest.json").write_text(
        json.dumps(packages, sort_keys=True, separators=(",", ":"))
    )

    package_index = dict(map(lambda p: (p[0], p[1]["version"]), packages.items()))

    (output_path / "index.json").write_text(
        json.dumps(
            {
                "architecture": packages["base-files"]["architecture"],
                "packages": package_index,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    current_app.logger.info(f"{version}: found {len(package_index.keys())} packages")


def update_arch_packages(branch: dict, arch: str):
    current_app.logger.info(f"Update {branch['name']}/{arch}")
    r = get_redis()

    packages_path = branch["path_packages"].format(branch=branch["name"])
    if not is_modified(
        current_app.config["UPSTREAM_URL"] + f"/{packages_path}/{arch}/feeds.conf"
    ):
        current_app.logger.debug(f"{branch['name']}/{arch}: Skip package update")
        return

    packages = {}

    # first update extra repos in case they contain redundant packages to core
    for name, url in branch.get("extra_repos", {}).items():
        current_app.logger.debug(f"Update extra repo {name} at {url}")
        packages.update(parse_packages_file(f"{url}/Packages.manifest", name))

    # update default repositories afterwards so they overwrite redundancies
    for repo in branch["repos"]:
        repo_packages = get_packages_arch_repo(branch, arch, repo)
        current_app.logger.debug(
            f"{branch['name']}/{arch}/{repo}: Found {len(repo_packages)} packages"
        )
        packages.update(repo_packages)

    if len(packages) == 0:
        current_app.logger.warning(f"{branch['name']}/{arch}: No packages found")
        return

    output_path = current_app.config["JSON_PATH"] / packages_path
    output_path.mkdir(exist_ok=True, parents=True)

    (output_path / f"{arch}-manifest.json").write_text(
        json.dumps(packages, sort_keys=True, separators=(",", ":"))
    )

    package_index = dict(map(lambda p: (p[0], p[1]["version"]), packages.items()))

    (output_path / f"{arch}-index.json").write_text(
        json.dumps(package_index, sort_keys=True, separators=(",", ":"))
    )

    current_app.logger.info(f"{arch}: found {len(package_index.keys())} packages")
    update_set(f"packages:{branch['name']}:{arch}", *package_index.keys())

    virtual_packages = {
        vpkg.split("=")[0]
        for pkg in packages.values()
        if (provides := pkg.get("provides"))
        for vpkg in provides.split(", ")
    }
    r.sadd(f"packages:{branch['name']}:{arch}", *(virtual_packages | packages.keys()))


def update_target_profiles(branch: dict, version: str, target: str) -> str:
    """Update available profiles of a specific version

    Args:
        branch(dict): Containing all branch information as defined in BRANCHES
        version(str): Version within branch
        target(str): Target within version
    """
    current_app.logger.info(f"{version}/{target}: Update profiles")
    r = get_redis()
    version_path = branch["path"].format(version=version)

    profiles_url = (
        current_app.config["UPSTREAM_URL"]
        + f"/{version_path}/targets/{target}/profiles.json"
    )

    req = requests.get(profiles_url)

    if req.status_code != 200:
        current_app.logger.warning("Couldn't download %s", profiles_url)
        return False

    metadata = req.json()
    profiles = metadata.pop("profiles", {})

    if not is_modified(profiles_url):
        current_app.logger.debug(f"{version}/{target}: Skip profiles update")
        return metadata["arch_packages"]

    r.hset(f"architecture:{branch['name']}", target, metadata["arch_packages"])

    queue = Queue(connection=r)
    registry = FinishedJobRegistry(queue=queue)
    version_code = r.get(f"revision:{version}:{target}")
    if version_code:
        version_code = version_code.decode()
        for request_hash in r.smembers(f"builds:{version_code}:{target}"):
            current_app.logger.warning(
                f"{version_code}/{target}: Delete outdated job build"
            )
            try:
                request_hash = request_hash.decode()
                registry.remove(request_hash, delete_job=True)
                rmtree(current_app.config["STORE_PATH"] / request_hash)

            except NoSuchJobError:
                current_app.logger.warning("Job was already deleted")
        r.delete(f"builds:{version_code}:{target}")

    r.set(
        f"revision:{version}:{target}",
        metadata["version_code"],
    )

    current_app.logger.info(f"{version}/{target}: Found {len(profiles)} profiles")

    pipeline = r.pipeline(True)
    pipeline.delete(f"profiles:{branch['name']}:{version}:{target}")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            if not r.hexists(f"mapping:{branch['name']}:{version}:{target}", supported):
                current_app.logger.info(
                    f"{version}/{target}: Add profile mapping {supported} -> {profile}"
                )
                r.hset(
                    f"mapping:{branch['name']}:{version}:{target}", supported, profile
                )

        pipeline.sadd(f"profiles:{branch['name']}:{version}:{target}", profile)

        profile_path = (
            current_app.config["JSON_PATH"]
            / version_path
            / "targets"
            / target
            / profile
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

    return metadata["arch_packages"]


def update_meta_json():
    latest = list(
        map(
            lambda b: b["versions"][0],
            filter(
                lambda b: b.get("enabled"),
                current_app.config["BRANCHES"].values(),
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
                            get_redis().hgetall(f"architecture:{b['name']}").items(),
                        )
                    ),
                },
            ),
            filter(
                lambda b: b.get("enabled"),
                current_app.config["BRANCHES"].values(),
            ),
        )
    )

    current_app.config["OVERVIEW"] = {
        "latest": latest,
        "branches": branches,
        "server": {
            "version": __version__,
            "contact": "mail@aparcar.org",
            "allow_defaults": current_app.config["ALLOW_DEFAULTS"],
        },
    }

    (current_app.config["JSON_PATH"] / "overview.json").write_text(
        json.dumps(
            current_app.config["OVERVIEW"],
            indent=2,
        )
    )

    (current_app.config["JSON_PATH"] / "branches.json").write_text(
        json.dumps(list(branches.values()))
    )

    (current_app.config["JSON_PATH"] / "latest.json").write_text(
        json.dumps({"latest": latest})
    )


@bp.cli.command("update")
@click.option("-i", "--interval", default=10, type=int)
def update(interval):
    """Update the data required to run the server

    For this all available packages and profiles for all enabled versions is
    downloaded and stored in the Redis database.
    """
    current_app.logger.info("Init ASU janitor")
    while True:
        if not current_app.config["BRANCHES"]:
            current_app.logger.error(
                "No BRANCHES defined in config, nothing to do, exiting"
            )
            return
        for branch in current_app.config["BRANCHES"].values():
            if not branch.get("enabled"):
                current_app.logger.info(f"{branch['name']}: Skip disabled branch")
                continue

            current_app.logger.info(f"Update {branch['name']}")
            update_branch(branch)

        update_meta_json()

        if interval > 0:
            current_app.logger.info(f"Next reload in { interval } minutes")
            sleep(interval * 60)
        else:
            current_app.logger.info("Exiting ASU janitor")
            break
