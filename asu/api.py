from flask import request, g, current_app, Blueprint
from rq import Connection, Queue
from uuid import uuid4

from .build import build
from .common import get_request_hash

bp = Blueprint("api", __name__, url_prefix="/api")


def get_distros():
    return ["openwrt"]


def get_versions():
    if "versions" not in g:
        g.versions = current_app.config["VERSIONS"]
        current_app.logger.info(f"Loaded {len(g.versions)} versions")
    return g.versions


def get_redis():
    if "redis" not in g:
        g.redis = current_app.config["REDIS_CONN"]
    return g.redis


def get_queue():
    if "queue" not in g:
        with Connection():
            g.queue = Queue(connection=get_redis())
    return g.queue


def validate_request(request_data):
    for needed in ["version", "profile"]:
        if needed not in request_data:
            return ({"status": "bad_request", "message": f"Missing {needed}"}, 400)

    if request_data.get("distro", "openwrt") not in get_distros():
        return (
            {
                "status": "bad_distro",
                "message": f"Unknown distro: {request_data['distro']}",
            },
            400,
        )

    if request_data.get("version", "") not in get_versions().keys():
        return (
            {
                "status": "bad_version",
                "message": f"Unknown version: {request_data['version']}",
            },
            400,
        )

    target = get_redis().hget(
        f"profiles-{request_data['version']}", request_data["profile"]
    )

    if not target:
        return (
            {
                "status": "bad_profile",
                "message": f"Unknown profile: {request_data['profile']}",
            },
            400,
        )
    else:
        request_data["target"] = target

    if "packages" in request_data:
        request_data["packages"] = set(request_data["packages"])

        # store request packages temporary in Redis and create a diff
        temp = str(uuid4())
        pipeline = get_redis().pipeline(True)
        pipeline.sadd(temp, *set(map(lambda p: p.strip("-"), request_data["packages"])))
        pipeline.expire(temp, 5)
        pipeline.sdiff(temp, f"packages-{request_data['version']}")
        unknown_packages = list(map(lambda u: u.decode(), pipeline.execute()[-1]))

        if unknown_packages:
            return (
                {
                    "status": "bad_packages",
                    "message": f"Unknown package(s): {', '.join(unknown_packages)}",
                },
                422,
            )
    else:
        request_data["packages"] = set()

    return ({}, None)


@bp.route("/versions")
def api_versions():
    return get_versions()


def return_job(job):
    response = {}
    if job.meta:
        response.update(job.meta)

    if job.is_failed:
        status = 500
        response["message"] = job.exc_info.strip().split("\n")[-1]

    if job.is_queued or job.is_started:
        status = 202
        response = {"status": job.get_status()}

    if job.is_finished:
        status = 200
        response.update(job.result)
        response["build_at"] = job.ended_at

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    current_app.logger.debug(f"Response {response} with status {status}")
    return response, status


@bp.route("/build/<request_hash>", methods=["GET"])
def api_build_get(request_hash):
    job = get_queue().fetch_job(request_hash)
    if not job:
        return {"status": "not_found"}, 404

    return return_job(job)


@bp.route("/build", methods=["POST"])
def api_build():
    request_data = request.get_json()
    current_app.logger.debug("rerequest_data {request_data}")
    if not request_data:
        return {"status": "bad_request"}, 400

    request_hash = get_request_hash(request_data)
    job = get_queue().fetch_job(request_hash)
    response = {}
    status = 200
    if not current_app.config["DEBUG"]:
        result_ttl = "24h"
        failure_ttl = "12h"
    else:
        result_ttl = "15m"
        failure_ttl = "15m"

    if job is None:
        response, status = validate_request(request_data)
        if response:
            return response, status

        request_data["store_path"] = current_app.config["STORE_PATH"]
        request_data["upstream_url"] = current_app.config["UPSTREAM_URL"]
        request_data["version_data"] = current_app.config["VERSIONS"][
            request_data["version"]
        ]

        job = get_queue().enqueue(
            build,
            request_data,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
        )

    return return_job(job)
