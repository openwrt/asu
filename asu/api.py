from flask import Blueprint, current_app, g, jsonify, redirect, request
from rq import Connection, Queue

from asu.build import build
from asu.common import get_branch, get_redis_client, get_request_hash, update

bp = Blueprint("api", __name__, url_prefix="/api")


def get_distros() -> list:
    """Return available distrobutions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


def redis_client():
    """Return Redis connectio

    Returns:
        Redis: Configured used Redis connection
    """
    if "redis" not in g:
        g.redis = get_redis_client(current_app.config)
    return g.redis


def get_queue() -> Queue:
    """Return the current queue

    Returns:
        Queue: The current RQ work queue
    """
    if "queue" not in g:
        with Connection():
            g.queue = Queue(
                connection=redis_client(), is_async=current_app.config["ASYNC_QUEUE"]
            )
    return g.queue


def api_v1_revision(version, target, subtarget):
    return jsonify(
        {
            "revision": redis_client()
            .get(f"revision:{version}:{target}/{subtarget}")
            .decode()
        }
    )


# tbd
@bp.route("/latest")
def api_latest():
    return redirect("/json/v1/latest.json")


@bp.route("/overview")
def api_v1_overview():
    return redirect("/json/v1/overview.json")


def validate_request(req):
    """Validate an image request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version and package.

    Args:
        req (dict): The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """

    if req.get("defaults") and not current_app.config["ALLOW_DEFAULTS"]:
        return (
            {"detail": "Handling `defaults` not enabled on server", "status": 400},
            400,
        )

    req["distro"] = req.get("distro", "openwrt")
    if req["distro"] not in get_distros():
        return (
            {"detail": f"Unsupported distro: {req['distro']}", "status": 400},
            400,
        )

    req["branch"] = get_branch(req["version"])

    r = redis_client()

    if not r.sismember("branches", req["branch"]):
        return (
            {"detail": f"Unsupported branch: {req['version']}", "status": 400},
            400,
        )

    if not r.sismember(f"versions:{req['branch']}", req["version"]):
        return (
            {"detail": f"Unsupported version: {req['version']}", "status": 400},
            400,
        )

    req["packages"] = list(
        map(
            lambda x: x.removeprefix("+"),
            sorted(req.get("packages_versions", {}).keys() or req.get("packages", [])),
        )
    )

    current_app.logger.debug("Profile before mapping " + req["profile"])

    if not r.hexists(f"targets:{req['branch']}", req["target"]):
        return ({"detail": f"Unsupported target: {req['target']}", "status": 400}, 400)

    if req["target"] in [
        "x86/64",
        "x86/generic",
        "x86/geode",
        "x86/legacy",
        "armsr/armv7",
        "armsr/armv8",
    ]:
        current_app.logger.debug("Use generic profile for {req['target']}")
        req["profile"] = "generic"
    else:
        if r.sismember(
            f"profiles:{req['branch']}:{req['version']}:{req['target']}",
            req["profile"].replace(",", "_"),
        ):
            req["profile"] = req["profile"].replace(",", "_")
        else:
            mapped_profile = r.hget(
                f"mapping:{req['branch']}:{req['version']}:{req['target']}",
                req["profile"],
            )

            if mapped_profile:
                req["profile"] = mapped_profile.decode()
            else:
                return (
                    {"detail": f"Unsupported profile: {req['profile']}", "status": 400},
                    400,
                )

    return ({}, None)


def return_job_v1(job):
    response = job.get_meta()
    headers = {}
    if job.meta:
        response.update(job.meta)

    if job.is_failed:
        response.update({"status": 500, "error": job.latest_result().exc_string})

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
        headers = {"X-Imagebuilder-Status": response.get("imagebuilder_status", "init")}

    elif job.is_finished:
        response.update({"status": 200, **job.result})

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    current_app.logger.debug(response)
    return response, response["status"], headers


def api_v1_update(version, target, subtarget):
    if current_app.config.get("UPDATE_TOKEN") == request.headers.get("X-Update-Token"):
        config = {
            "JSON_PATH": current_app.config["PUBLIC_PATH"] / "json/v1",
            "BRANCHES": current_app.config["BRANCHES"],
            "UPSTREAM_URL": current_app.config["UPSTREAM_URL"],
            "ALLOW_DEFAULTS": current_app.config["ALLOW_DEFAULTS"],
            "REPOSITORY_ALLOW_LIST": current_app.config["REPOSITORY_ALLOW_LIST"],
            "REDIS_URL": current_app.config["REDIS_URL"],
        }
        get_queue().enqueue(
            update,
            config=config,
            version=version,
            target=f"{target}/{subtarget}",
            job_timeout="10m",
        )

        return None, 204
    else:
        return {"status": 403, "detail": "Forbidden"}, 403


# legacy offering /api/overview
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
    if req.get("defaults"):
        result_ttl = "1h"
    failure_ttl = "12h"

    if "client" in req:
        redis_client().hincrby("stats:clients", req["client"])
    else:
        if request.headers.get("user-agent").startswith("auc"):
            redis_client().hincrby(
                "stats:clients",
                request.headers.get("user-agent").replace(" (", "/").replace(")", ""),
            )
        else:
            redis_client().hincrby("stats:clients", "unknown/0")

    if job is None:
        redis_client().incr("stats:cache-miss")
        response, status = validate_request(req)
        if response:
            return response, status

        req["public_path"] = str(current_app.config["PUBLIC_PATH"])
        req["branch_data"] = current_app.config["BRANCHES"][req["branch"]]
        req["repository_allow_list"] = current_app.config["REPOSITORY_ALLOW_LIST"]
        req["request_hash"] = request_hash

        job = get_queue().enqueue(
            build,
            req,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="10m",
        )
    else:
        if job.is_finished:
            redis_client().incr("stats:cache-hit")

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
        response["message"] = job.meta["detail"]

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

        req["public_path"] = current_app.config["PUBLIC_PATH"]
        if current_app.config.get("CACHE_PATH"):
            req["cache_path"] = current_app.config.get("CACHE_PATH")
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
