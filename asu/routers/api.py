import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from asu.build import build
from asu.config import settings
from asu.update import update
from asu.util import get_branch, get_queue, get_redis_client, get_request_hash

router = APIRouter()


class BuildRequest(BaseModel):
    distro: str = "openwrt"
    version: str
    target: str
    packages: Optional[list] = []
    profile: str
    packages_versions: dict = {}
    defaults: Optional[
        Annotated[
            str,
            Field(
                default=None,
                max_length=settings.max_defaults_length,
                description="Custom shell script embedded in firmware image to be run on first\n"
                "boot. This feature might be dropped in the future. Input file size\n"
                f"is limited to {settings.max_defaults_length} bytes and cannot be exceeded.",
            ),
        ]
    ] = None
    client: Optional[str] = "unknown/0"
    rootfs_size_mb: Optional[
        Annotated[
            int,
            Field(
                default=None,
                ge=1,
                le=settings.max_custom_rootfs_size_mb,
                description="Ability to specify a custom CONFIG_TARGET_ROOTFS_PARTSIZE for the\n"
                "resulting image. Attaching this optional parameter will cause\n"
                "ImageBuilder to build a rootfs with that size in MB.",
            ),
        ]
    ] = None
    diff_packages: Optional[bool] = False


def get_distros() -> list:
    """Return available distributions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


@router.get("/revision/{version}/{target}/{subtarget}")
def api_v1_revision(version: str, target: str, subtarget: str):
    return {
        "revision": get_redis_client()
        .get(f"revision:{version}:{target}/{subtarget}")
        .decode("utf-8")
    }


@router.get("/latest")
def api_latest():
    return RedirectResponse("/json/v1/latest.json", status_code=301)


@router.get("/overview")
def api_v1_overview():
    return RedirectResponse("/json/v1/overview.json", status_code=301)


def validate_request(req):
    """Validate an image request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version and package.

    Args:
        req (dict): The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """

    if req.get("defaults") and not settings.allow_defaults:
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

    req["branch"] = get_branch(req["version"])["name"]

    r = get_redis_client()

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

    logging.debug("Profile before mapping " + req["profile"])

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
        logging.debug("Use generic profile for {req['target']}")
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
        response.update({"status": 200, **job.return_value()})

    response["enqueued_at"] = job.enqueued_at
    response["request_hash"] = job.id

    logging.debug(response)
    return response, response["status"], headers


@router.get("/update/{version}/{target}/{subtarget}")
def api_v1_update(
    version: str,
    target: str,
    subtarget: str,
    response: Response,
    x_update_token: Annotated[str | None, Header()] = None,
):
    token = settings.update_token
    if token and token == x_update_token:
        get_queue().enqueue(
            update,
            version=version,
            target_subtarget=f"{target}/{subtarget}",
            job_timeout="10m",
        )
        response.status_code = 204
        return None
    else:
        response.status_code = 403
        return {"status": 403, "detail": "Forbidden"}


@router.get("/build/{request_hash}")
def api_v1_build_get(request_hash: str, response: Response):
    job = get_queue().fetch_job(request_hash)
    if not job:
        response.status_code = 404
        return {
            "status": 404,
            "title": "Not Found",
            "detail": "could not find provided request hash",
        }

    content, status, headers = return_job_v1(job)
    response.headers.update(headers)
    response.status_code = status

    return content


@router.post("/build")
def api_v1_build_post(
    build_request: BuildRequest,
    response: Response,
    user_agent: str = Header(None),
):
    request_hash = get_request_hash(build_request.dict())
    job = get_queue().fetch_job(request_hash)
    status = 200
    result_ttl = "7d"
    if build_request.defaults:
        result_ttl = "1h"
    failure_ttl = "12h"

    if build_request.client:
        get_redis_client().hincrby("stats:clients", build_request.client)
    else:
        if user_agent.startswith("auc"):
            get_redis_client().hincrby(
                "stats:clients",
                user_agent.replace(" (", "/").replace(")", ""),
            )
        else:
            get_redis_client().hincrby("stats:clients", "unknown/0")

    if job is None:
        get_redis_client().incr("stats:cache-miss")
        req = build_request.dict()
        content, status = validate_request(req)
        if content:
            response.status_code = status
            return content

        req["public_path"] = str(settings.public_path)
        req["repository_allow_list"] = settings.repository_allow_list
        req["request_hash"] = request_hash
        req["base_container"] = settings.base_container

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
            get_redis_client().incr("stats:cache-hit")

    content, status, headers = return_job_v1(job)
    response.headers.update(headers)
    response.status_code = status

    return content
