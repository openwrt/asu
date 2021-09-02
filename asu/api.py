from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, redirect, request
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


def get_redis():
    """Return Redis connectio

    Returns:
        Redis: Configured used Redis connection
    """
    if "redis" not in g:
        g.redis = current_app.config["REDIS_CONN"]
    return g.redis


def get_queue() -> Queue:
    """Return the current queue

    Returns:
        Queue: The current RQ work queue
    """
    if "queue" not in g:
        with Connection():
            g.queue = Queue(connection=get_redis())
    return g.queue


def api_v1_revision(version, target, subtarget):
    return jsonify(
        {
            "revision": get_redis()
            .get(f"revision-{version}-{target}/{subtarget}")
            .decode()
        }
    )


# tbd
@bp.route("/latest")
def api_latest():
    return redirect("/json/v1/latest.json")


def api_v1_stats_images():
    return jsonify({"images": int(get_redis().get("stats-images").decode("utf-8"))})


def api_v1_stats_versions():
    return jsonify(
        {
            "versions": [
                (s, p.decode("utf-8"))
                for p, s in get_redis().zrevrange(
                    f"stats-versions", 0, -1, withscores=True
                )
            ],
        }
    )


def api_v1_stats_targets(branch="SNAPSHOT"):
    if branch not in current_app.config["BRANCHES"]:
        return "", 404

    return jsonify(
        {
            "branch": branch,
            "targets": [
                (s, p.decode("utf-8"))
                for p, s in get_redis().zrevrange(
                    f"stats-targets-{branch}", 0, -1, withscores=True
                )
            ],
        }
    )


@bp.route("/v1/stats/targets/")
def api_v1_stats_targets_default():
    return redirect("/api/v1/stats/targets/SNAPSHOT")


def api_v1_stats_packages(branch="SNAPSHOT"):
    if branch not in current_app.config["BRANCHES"]:
        return "", 404

    return jsonify(
        {
            "branch": branch,
            "packages": [
                (s, p.decode("utf-8"))
                for p, s in get_redis().zrevrange(
                    f"stats-packages-{branch}", 0, -1, withscores=True
                )
            ],
        }
    )


@bp.route("/v1/stats/packages/")
def api_v1_stats_packages_default():
    return redirect("/api/v1/stats/packages/SNAPSHOT")


def api_v1_stats_profiles(branch):
    if branch not in current_app.config["BRANCHES"]:
        return "", 404

    return jsonify(
        {
            "branch": branch,
            "profiles": [
                (s, p.decode("utf-8"))
                for p, s in get_redis().zrevrange(
                    f"stats-profiles-{branch}", 0, -1, withscores=True
                )
            ],
        }
    )


@bp.route("/v1/stats/profiles/")
def api_v1_stats_profiles_default():
    return redirect("/api/v1/stats/profiles/SNAPSHOT")


def validate_packages(req):
    if req.get("packages_versions") and not req.get("packages"):
        req["packages"] = req["packages_versions"].keys()

    if not req.get("packages"):
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
                "detail": f"Unsupported package(s): {', '.join(unknown_packages)}",
                "status": 422,
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
    req["distro"] = req.get("distro", "openwrt")
    if req["distro"] not in get_distros():
        return (
            {"detail": f"Unsupported distro: {req['distro']}", "status": 400},
            400,
        )

    req["version"] = req["version"]

    if req["version"].endswith("-SNAPSHOT"):
        # e.g. 21.02-snapshot
        req["branch"] = req["version"].rsplit("-", maxsplit=1)[0]
    else:
        # e.g. snapshot, 21.02.0-rc1 or 19.07.7
        req["branch"] = req["version"].rsplit(".", maxsplit=1)[0]

    if req["branch"] not in current_app.config["BRANCHES"].keys():
        return (
            {"detail": f"Unsupported branch: {req['version']}", "status": 400},
            400,
        )

    if req["version"] not in current_app.config["BRANCHES"][req["branch"]]["versions"]:
        return (
            {"detail": f"Unsupported version: {req['version']}", "status": 400},
            400,
        )

    r = get_redis()

    current_app.logger.debug("Profile before mapping " + req["profile"])

    if not r.sismember(
        f"targets-{req['branch']}",
        req["target"],
    ):
        return (
            {"detail": f"Unsupported target: {req['target']}", "status": 400},
            400,
        )

    req["arch"] = current_app.config["BRANCHES"][req["branch"]]["targets"][
        req["target"]
    ]

    if req["target"] in ["x86/64", "x86/generic", "x86/geode", "x86/legacy"]:
        current_app.logger.debug("Use generic profile for {req['target']}")
        req["profile"] = "generic"
    else:
        mapped_profile = r.hget(
            f"mapping-{req['branch']}-{req['version']}-{req['target']}",
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
                {"detail": f"Unsupported profile: {req['profile']}", "status": 400},
                400,
            )

    package_problems = validate_packages(req)
    if package_problems:
        return package_problems

    return ({}, None)


def return_job_v1(job):
    response = {}
    headers = {}
    if job.meta:
        response.update(job.meta)

    if job.is_failed:
        response.update({"status": 500, "detail": job.exc_info.strip().split("\n")[-1]})

    elif job.is_queued:
        response.update(
            {
                "status": 202,
                "detail": "queued",
                "queue_position": job.get_position() or 0,
            }
        )
        headers["X-Queue-Position"] = str(response["queue_position"])

    elif job.is_started:
        response.update(
            {
                "status": 202,
                "detail": "started",
            }
        )

    elif job.is_finished:
        return redirect(f"/store/{job.result}/build.json", code=301)

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    current_app.logger.debug(response)
    return response, response["status"], headers


def api_v1_overview():
    return jsonify(current_app.config["OVERVIEW"])


def api_v1_build_get(request_hash):
    job = get_queue().fetch_job(request_hash)
    if not job:
        return {
            "status": 404,
            "title": "Not Found",
            "detail": "could not find provided request hash",
        }, 404

    return return_job_v1(job)


def api_v1_build_post():
    req = request.get_json()
    current_app.logger.debug(f"req {req}")
    request_hash = get_request_hash(req)
    job = get_queue().fetch_job(request_hash)
    response = {}
    status = 200
    result_ttl = "7d"
    failure_ttl = "12h"

    if job is None:
        response, status = validate_request(req)
        if response:
            return response, status

        req["store_path"] = current_app.config["STORE_PATH"]
        req["upstream_url"] = current_app.config["UPSTREAM_URL"]
        req["branch_data"] = current_app.config["BRANCHES"][req["branch"]]
        req["request_hash"] = request_hash

        job = get_queue().enqueue(
            build,
            req,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="10m",
        )

    return return_job_v1(job)


# legacy /api/build
@bp.route("/branches")
def api_branches():
    return jsonify(list(current_app.config["OVERVIEW"]["branches"].values()))


def return_job(job):
    response = {}
    if job.meta:
        response.update(job.meta)

    status = 500

    if job.is_failed:
        response["message"] = job.exc_info.strip().split("\n")[-1]

    elif job.is_queued:
        status = 202
        response = {
            "status": job.get_status(),
            "queue_position": job.get_position() or 0,
        }

    elif job.is_started:
        status = 202
        response = {
            "status": job.get_status(),
        }

    elif job.is_finished:
        status = 200
        response.update(job.result)
        response["build_at"] = job.ended_at

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    current_app.logger.debug(f"Response {response} with status {status}")
    return response, status


@bp.route("/build/<path:request_hash>", methods=["GET"])
def api_build_get(request_hash):
    job = get_queue().fetch_job(request_hash)
    if not job:
        return {"status": "not_found"}, 404

    return return_job(job)


@bp.route("/build", methods=["POST"])
def api_build_post():
    req = request.get_json()
    current_app.logger.debug(f"req {req}")
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
        req["branch_data"] = current_app.config["BRANCHES"][req["branch"]]
        req["request_hash"] = request_hash

        job = get_queue().enqueue(
            build,
            req,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="10m",
        )

    return return_job(job)
