from uuid import uuid4
from flask import request, g, current_app, Blueprint
from rq import Connection, Queue

from .build import build
from .common import get_request_hash

bp = Blueprint("api", __name__, url_prefix="/api")


def get_distros() -> list:
    """Return available distrobutions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


@bp.route("/branches")
def get_branches() -> dict:
    if "branches" not in g:
        g.branches = {}
        for branch in current_app.config["BRANCHES"]:
            if branch["enabled"]:
                g.branches[branch["name"]] = branch
        current_app.logger.info(f"Loaded {len(g.branches)} branches")
    return g.branches


def get_redis():
    """Return Redis connectio

    Returns:
        Redis: Configured used Redis connection
    """
    if "redis" not in g:
        g.redis = current_app.config["REDIS_CONN"]
    return g.redis


def get_latest() -> dict:
    if "latest" not in g:
        g.latest = list(
            map(
                lambda b: b["versions"][0],
                filter(
                    lambda b: b.get("enabled"),
                    current_app.config["BRANCHES"],
                ),
            )
        )

    return g.latest


@bp.route("/latest")
def api_latest():
    return {"latest": get_latest()}


def get_queue() -> Queue:
    """Return the current queue

    Returns:
        Queue: The current RQ work queue
    """
    if "queue" not in g:
        with Connection():
            g.queue = Queue(connection=get_redis())
    return g.queue


def validate_packages(req):
    if "packages" in req and "packages_versions" in req:
        return (
            {
                "status": "duplicate_package_list",
                "message": "Use either `packages` or `packages_versions`, not both",
            },
            400,
        )
    elif req.get("packages"):
        pass
    elif req.get("packages_versions"):
        req["packages"] = req["packages_versions"].keys()
    else:
        # no packages to check
        return

    req["packages"] = set(req["packages"]) - {"kernel", "libc", "libgcc"}

    r = get_redis()

    # translate packages to remove their ABI version for 19.07.x compatibility
    tr = set()
    for p in req["packages"]:
        p_tr = r.hget("mapping-abi", p)
        if p_tr:
            tr.add(p_tr.decode())
        else:
            tr.add(p)

    req["packages"] = tr

    # store request packages temporary in Redis and create a diff
    temp = str(uuid4())
    pipeline = r.pipeline(True)
    pipeline.sadd(temp, *set(map(lambda p: p.strip("-"), req["packages"])))
    pipeline.expire(temp, 5)
    pipeline.sdiff(
        temp,
        f"packages-{req['branch']}-{req['version']}-{req['target']}",
        f"packages-{req['branch']}-{req['arch']}",
    )
    unknown_packages = list(map(lambda p: p.decode(), pipeline.execute()[-1]))

    if unknown_packages:
        return (
            {
                "status": "bad_packages",
                "message": f"Unsupported package(s): {', '.join(unknown_packages)}",
            },
            422,
        )


def validate_request(req):
    """Validate an image request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version and package.

    Args:
        req (dict): The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """
    for needed in ["version", "target", "profile"]:
        if needed not in req:
            return ({"status": "bad_request", "message": f"Missing {needed}"}, 400)

    req["distro"] = req.get("distro", "openwrt")
    if req["distro"] not in get_distros():
        return (
            {
                "status": "bad_distro",
                "message": f"Unsupported distro: {req['distro']}",
            },
            400,
        )

    req["version"] = req["version"]

    if req["version"].endswith("-SNAPSHOT"):
        # e.g. 21.02-snapshot
        req["branch"] = req["version"].rsplit("-", maxsplit=1)[0]
    else:
        # e.g. snapshot, 21.02.0-rc1 or 19.07.7
        req["branch"] = req["version"].rsplit(".", maxsplit=1)[0]

    if req["branch"] not in get_branches().keys():
        return (
            {
                "status": "bad_branch",
                "message": f"Unsupported branch: {req['version']}",
            },
            400,
        )

    if req["version"] not in get_branches()[req["branch"]]["versions"]:
        return (
            {
                "status": "bad_version",
                "message": f"Unsupported version: {req['version']}",
            },
            400,
        )

    r = get_redis()

    current_app.logger.debug("Profile before mapping " + req["profile"])

    if not r.sismember(
        f"targets-{req['branch']}",
        req["target"],
    ):
        return (
            {
                "status": "bad_target",
                "message": f"Unsupported target: {req['target']}",
            },
            400,
        )

    req["arch"] = get_branches()[req["branch"]]["targets"][req["target"]]

    if req["target"] in ["x86/64", "x86/generic", "x86/geode", "x86/legacy"]:
        current_app.logger.debug("Use generic profile for {req['target']}")
        req["profile"] = "generic"
    else:
        mapped_profile = r.hget(
            f"mapping-{req['branch']}-{req['version']}",
            req["profile"],
        )

        if mapped_profile:
            req["profile"] = mapped_profile.decode()

        current_app.logger.debug("Profile after mapping " + req["profile"])

        if not r.sismember(
            f"profiles-{req['branch']}-{req['version']}-{req['target']}",
            req["profile"],
        ):
            return (
                {
                    "status": "bad_profile",
                    "message": f"Unsupported profile: {req['profile']}",
                },
                400,
            )

    package_problems = validate_packages(req)
    if package_problems:
        return package_problems

    return ({}, None)


def return_job(job):
    """Return job status message and code

    The states vary if the image is currently build, failed or finished

    Returns:
        (dict, int): Status message and code
    """
    response = {}
    if job.meta:
        response.update(job.meta)

    if job.is_failed:
        status = 500
        response["message"] = job.exc_info.strip().split("\n")[-1]

    elif job.is_queued or job.is_started:
        status = 202
        response = {"status": job.get_status(), "queue_position": job.get_position()}

    elif job.is_finished:
        status = 200
        response.update(job.result)
        response["build_at"] = job.ended_at

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    current_app.logger.debug(f"Response {response} with status {status}")
    return response, status


@bp.route("/build/<request_hash>", methods=["GET"])
def api_build_get(request_hash):
    """API call to get job information based on `request_hash`

    This API call can be used for polling once the initial build request is
    accepted. The request using POST returns the `request_hash` on success.

    Args:
        request_hash (str): Request hash to lookup

    Retrns:
        (dict, int): Status message and code
    """
    job = get_queue().fetch_job(request_hash)
    if not job:
        return {"status": "not_found"}, 404

    return return_job(job)


@bp.route("/build", methods=["POST"])
def api_build():
    """API call to request an image

    An API request contains at least version and profile. The `packages` key
    can contain a list of extra packages to install.

    Below an example of the contents of the POSTed JSON data:

        {
            "profile": "tplink_tl-wdr4300-v1",
            "packages": [
                "luci"
            ],
            "version": "SNAPSHOT"
        }

    Retrns:
        (dict, int): Status message and code
    """
    req = request.get_json()
    current_app.logger.debug(f"req {req}")
    if not req:
        return {"status": "bad_request"}, 400

    request_hash = get_request_hash(req)
    job = get_queue().fetch_job(request_hash)
    response = {}
    status = 200
    result_ttl = "24h"
    failure_ttl = "12h"

    if job is None:
        response, status = validate_request(req)
        if response:
            return response, status

        req["store_path"] = current_app.config["STORE_PATH"]
        req["upstream_url"] = current_app.config["UPSTREAM_URL"]
        req["branch_data"] = get_branches()[req["branch"]]

        job = get_queue().enqueue(
            build,
            req,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="10m",
        )

    return return_job(job)
