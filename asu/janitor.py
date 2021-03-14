import requests
from multiprocessing import Pool

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
            package_name = package.get("SourceName")
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
    r = get_redis()

    targets = branch["targets"].keys()

    if len(targets) == 0:
        current_app.logger.warning("No targets found for {branch['name']}")
        return

    r.sadd(f"targets-{branch['name']}", *list(targets))

    architectures = set(branch["targets"].values())

    with Pool(20) as pool:
        pool.starmap(update_arch_packages, map(lambda a: (branch, a), architectures))

    for version in branch["versions"]:
        current_app.logger.info(f"Update {branch['name']}/{version}")
        with Pool() as pool:
            # TODO: ugly
            version_path = branch["path"].format(version=version)
            version_path_abs = current_app.config["JSON_PATH"] / version_path
            packages_path = branch["path_packages"].format(branch=branch["name"])
            output_path = current_app.config["JSON_PATH"] / packages_path
            version_path_abs.mkdir(exist_ok=True, parents=True)
            packages_symlink = version_path_abs / "packages"

            if not packages_symlink.exists():
                packages_symlink.symlink_to(output_path)

            pool.starmap(
                update_target_packages, map(lambda t: (branch, version, t), targets)
            )
            pool.starmap(
                update_target_profiles, map(lambda t: (branch, version, t), targets)
            )

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


def update_target_packages(branch: dict, version: str, target: str):
    current_app.logger.info(f"Updating packages of {branch['name']}")
    version_path = branch["path"].format(version=version)
    r = get_redis()

    packages = get_packages_target_base(branch, branch["versions"][0], target)

    if len(packages) == 0:
        current_app.logger.warning(f"No packages found for {target}")
        return

    r.sadd(f"packages-{branch['name']}-{version}-{target}", *list(packages.keys()))

    output_path = current_app.config["JSON_PATH"] / version_path / "targets" / target
    output_path.mkdir(exist_ok=True, parents=True)

    (output_path / "manifest.json").write_text(
        json.dumps(packages, sort_keys=True, separators=(",", ":"))
    )

    package_index = dict(map(lambda p: (p[0], p[1]["version"]), packages.items()))

    (output_path / "index.json").write_text(
        json.dumps(
            {
                "architecture": branch["targets"][target],
                "packages": package_index,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    current_app.logger.info(f"{version}: found {len(package_index.keys())} packages")
    r.sadd(f"packages-{branch['name']}-{version}", *package_index.keys())


def update_arch_packages(branch: dict, arch: str):
    current_app.logger.info(f"Update {branch['name']}/{arch}")
    r = get_redis()
    packages = {}
    packages_path = branch["path_packages"].format(branch=branch["name"])

    # first update extra repos in case they contain redundant packages to core
    for name, url in branch.get("extra_repos", {}).items():
        current_app.logger.debug(f"Update extra repo {name} at {url}")
        packages.update(parse_packages_file(f"{url}/Packages.manifest", name))

    # update default repositories afterwards so they overwrite redundancies
    for repo in branch["repos"]:
        packages.update(get_packages_arch_repo(branch, arch, repo))

    if len(packages) == 0:
        current_app.logger.warning(f"No packages found for {arch}")
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
    r.sadd(f"packages-{branch['name']}-{arch}", *package_index.keys())


def update_target_profiles(branch: dict, version: str, target: str):
    """Update available profiles of a specific version

    Args:
        branch(dict): Containing all branch information as defined in BRANCHES
        version(str): Version within branch
        target(str): Target within version
    """
    current_app.logger.info(f"Checking profiles of {branch['name']}/{version}/{target}")
    r = get_redis()
    version_path = branch["path"].format(version=version)
    req = requests.head(
        current_app.config["UPSTREAM_URL"]
        + f"/{version_path}/targets/{target}/profiles.json"
    )
    if req.status_code != 200:
        current_app.logger.warning(f"Could not download profiles.json for {target}")
        return

    req = requests.get(
        current_app.config["UPSTREAM_URL"]
        + f"/{version_path}/targets/{target}/profiles.json"
    )

    metadata = req.json()
    profiles = metadata.pop("profiles", {})

    current_app.logger.info(f"Found {len(profiles)} profiles")

    for profile, data in profiles.items():
        for supported in data.get("supported_devices", []):
            r.hset(f"mapping-{branch['name']}-{version}", supported, profile)
        r.hset(f"profiles-{branch['name']}-{version}", profile, target)
        profile_path = (
            current_app.config["JSON_PATH"]
            / version_path
            / "targets"
            / target
            / profile
        ).with_suffix(".json")
        profile_path.parent.mkdir(exist_ok=True, parents=True)
        profile_path.write_text(
            json.dumps({**data, **metadata}, sort_keys=True, separators=(",", ":"))
        )

        data["target"] = target


@bp.cli.command("update")
def update():
    """Update the data required to run the server

    For this all available packages and profiles for all enabled versions is
    downloaded and stored in the Redis database.
    """
    current_app.logger.info("Init ASU")

    for branch in current_app.config["BRANCHES"]:
        if not branch.get("enabled"):
            current_app.logger.info(f"Skip disabled version {branch['name']}")
            continue

        current_app.logger.info(f"Update {branch['name']}")
        update_branch(branch)
