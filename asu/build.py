import logging
from datetime import datetime
from shutil import rmtree

from rq import get_current_job

from .common import get_packages_hash
from .imagebuilder import ImageBuilder

log = logging.getLogger("rq.worker")


def set_stats(job, ib, req):
    job.connection.hincrby(
        "stats:builds",
        "#".join(
            [req["branch_data"]["name"], req["version"], req["target"], req["profile"]]
        ),
    )

    job.connection.sadd(
        f"builds:{ib.version_code}:{req['target']}", req["request_hash"]
    )


def create_build_json(ib, req, manifest):
    ib.profiles_json.update({"manifest": manifest})
    ib.profiles_json.update(ib.profiles_json["profiles"][req["profile"]])
    ib.profiles_json["id"] = req["profile"]
    ib.profiles_json["bin_dir"] = str(ib.bin_dir)
    ib.profiles_json.pop("profiles")
    ib.profiles_json["build_at"] = datetime.utcfromtimestamp(
        int(ib.profiles_json.get("source_date_epoch", 0))
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    ib.profiles_json["detail"] = "done"


def cleanup_imagebuilders(job, req):
    now_timestamp = int(datetime.now().timestamp())

    # Set last build timestamp for current target/subtarget to now
    job.connection.hset(
        f"worker:{job.worker_name}:last_build", req["target"], now_timestamp
    )

    # Iterate over all targets of the worker and remove the once inactive for a week
    for target_subtarget, last_build_timestamp in job.connection.hgetall(
        f"worker:{job.worker_name}:last_build"
    ).items():
        target_subtarget = target_subtarget.decode()

        log.debug("now_timestamp        %s %s", target_subtarget, now_timestamp)
        log.debug(
            "last_build_timestamp %s %s",
            target_subtarget,
            last_build_timestamp.decode(),
        )

        if now_timestamp - int(last_build_timestamp.decode()) > 60 * 60 * 24:
            log.info("Removing unused ImageBuilder for %s", target_subtarget)
            job.connection.hdel(
                f"worker:{job.worker_name}:last_build", target_subtarget
            )
            if (req["cache_path"] / target_subtarget).exists():
                rmtree(req["cache_path"] / target_subtarget)
                for suffix in [".stamp", ".sha256sums", ".sha256sums.sig"]:
                    (req["cache_path"] / target_subtarget).with_suffix(suffix).unlink(
                        missing_ok=True
                    )
        else:
            log.debug("Keeping ImageBuilder for %s", target_subtarget)


def build(req: dict):
    """Build image request and setup ImageBuilders automatically

    The `request` dict contains properties of the requested image.

    Args:
        request (dict): Contains all properties of requested image
    """

    job = get_current_job()

    def report_error(msg):
        log.warning(f"Error: {msg}")
        job.meta["detail"] = f"Error: {msg}"
        job.save_meta()
        raise

    if not req["store_path"].is_dir():
        report_error(f"Store path missing: {req['store_path']}")

    job.meta["detail"] = "init"
    job.save_meta()

    log.debug(f"Building {req}")

    ib = ImageBuilder(
        version=req["version"],
        target=req["target"],
        upstream_url=req["upstream_url"],
        custom_public_key=req["branch_data"]["pubkey"],
        cache=req["cache_path"],
    )

    log.info(f"Building {req}")

    err = ib.setup()

    if err:
        job.meta["stdout"] = ib.stdout
        job.meta["stderr"] = ib.stderr
        job.meta["build_cmd"] = ib.build_cmd
        job.save_meta()
        raise err

    log.debug("Config at %s", ib.workdir / ".config")

    if "version_code" in req:
        if ib.version_code != req.get("version_code"):
            report_error(
                f"Received inncorrect version {ib.version_code} "
                f"(requested {req['version_code']})"
            )

    if req.get("diff_packages", False):
        remove_packages = (ib.default_packages | ib.profile_packages) - req["packages"]
        req["packages"] = req["packages"] | set(map(lambda p: f"-{p}", remove_packages))
    else:
        req["packages"] = []

    job.meta["imagebuilder_status"] = "calculate_packages_hash"
    job.save_meta()

    manifest = ib.manifest(req["profile"], req["packages"])

    for package, version in req.get("packages_versions", {}).items():
        if package not in manifest:
            report_error(f"Impossible package selection: {package} not in manifest")
        if version != manifest[package]:
            report_error(
                f"Impossible package selection: {package} version not as requested: "
                f"{version} vs. {manifest[package]}"
            )

    manifest_packages = manifest.keys()

    log.debug(f"Manifest Packages: {manifest_packages}")

    packages_hash = get_packages_hash(manifest_packages)
    log.debug(f"Packages Hash {packages_hash}")

    ib.bin_dir = req["store_path"] / req["request_hash"]
    ib.bin_dir.mkdir(parents=True, exist_ok=True)

    log.debug("Build command: %s", ib.build_cmd)

    job.meta["imagebuilder_status"] = "building_image"
    job.save_meta()

    log.debug(f"Running {' '.join(ib.build_cmd)}")

    ib.build(
        req["profile"],
        req["packages"],
        packages_hash,
        defaults=req.get("defaults"),
        filesystem=req.get("filesystem"),
    )

    job.meta["stdout"] = ib.stdout
    job.meta["stderr"] = ib.stderr
    job.meta["build_cmd"] = ib.build_cmd
    job.save_meta()

    if not ib.profiles_json:
        report_error("No JSON file found")

    if req["profile"] not in ib.profiles_json["profiles"]:
        report_error("Profile not found in JSON file")

    create_build_json(ib, req, manifest)

    log.debug("JSON content %s", ib.profiles_json)

    set_stats(job, ib, req)

    cleanup_imagebuilders(job, req)

    return ib.profiles_json
