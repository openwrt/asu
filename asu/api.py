from flask import request, g, current_app, Blueprint
from rq import Connection, Queue
from uuid import uuid4

from .build import build
from .common import get_request_hash

bp = Blueprint("api", __name__, url_prefix="/api")


def get_distros() -> list:
    """Return available distrobutions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


@bp.route("/debug/get_versions")
def get_versions() -> dict:
    """Return available versions

    The configuration stores a dict of versions containing additional
    information like public signing key and upstream path.

    Returns:
        dict: latest available version per branch
    """
    if "versions" not in g:
        g.versions = dict(
            map(
                lambda b: (b["name"], b),
                filter(
                    lambda b: b.get("enabled"),
                    current_app.config["VERSIONS"]["branches"],
                ),
            )
        )
        current_app.logger.info(f"Loaded {len(g.versions)} versions")
    return g.versions


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


def validate_request(request_data):
    """Validate an image request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version and package.

    Args:
        request_data (dict): The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """
    for needed in ["version", "profile"]:
        if needed not in request_data:
            return ({"status": "bad_request", "message": f"Missing {needed}"}, 400)

    request_data["distro"] = request_data.get("distro", "openwrt").lower()
    if request_data["distro"] not in get_distros():
        return (
            {
                "status": "bad_distro",
                "message": f"Unsupported distro: {request_data['distro']}",
            },
            400,
        )

    request_data["version"] = request_data["version"].lower()
    request_data["branch"] = request_data["version"].rsplit(".", maxsplit=1)[0]
    if request_data["branch"] not in get_versions().keys():
        return (
            {
                "status": "bad_version",
                "message": f"Unsupported version: {request_data['version']}",
            },
            400,
        )
    if request_data["version"] != get_versions()[request_data["branch"]][
        "latest"
    ] and not get_versions()[request_data["branch"]].get("support_legacy_versions"):
        return (
            {
                "status": "legacy_version",
                "message": "No legacy version support enabled",
            },
            400,
        )

    # The supported_devices variable on devices uses a "," instead of "_"
    # It is stored on device as board_name and send to the server for requests
    # To be compatible with the build system profiles replace the "," with "_"
    # TODO upstream request to store device profile on board
    request_data["profile"] = request_data["profile"].replace(",", "_")

    target = get_redis().hget(
        f"profiles-{request_data['branch']}", request_data["profile"]
    )
    if not target:
        return (
            {
                "status": "bad_profile",
                "message": f"Unsupported profile: {request_data['profile']}",
            },
            400,
        )
    else:
        request_data["target"] = target.decode()

    if request_data.get("packages"):
        request_data["packages"] = set(request_data["packages"]) - {"kernel", "libc"}

        # store request packages temporary in Redis and create a diff
        temp = str(uuid4())
        pipeline = get_redis().pipeline(True)
        pipeline.sadd(temp, *set(map(lambda p: p.strip("-"), request_data["packages"])))
        pipeline.expire(temp, 5)
        pipeline.sdiff(
            temp,
            f"packages-{request_data['branch']}",
            f"packages-{request_data['branch']}-{request_data['target']}",
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
    else:
        request_data["packages"] = set()

    return ({}, None)


@bp.route("/versions")
def api_versions():
    """API call to get available versions

    Returns:
        dict: Available versions in JSON format
    """
    return current_app.config["VERSIONS"]


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
        response = {"status": job.get_status()}

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
        request_data["cache_path"] = current_app.config["CACHE_PATH"]
        request_data["upstream_url"] = current_app.config["UPSTREAM_URL"]
        request_data["version_data"] = get_versions()[request_data["version"]]

        job = get_queue().enqueue(
            build,
            request_data,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="5m",
        )

    return return_job(job)
