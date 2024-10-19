import logging
from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse, Response
from rq.job import Job

from asu.build import build
from asu.build_request import BuildRequest
from asu.config import settings
from asu.update import update
from asu.util import (
    add_timestamp,
    get_branch,
    get_queue,
    get_redis_client,
    get_request_hash,
)

router = APIRouter()


def get_distros() -> list:
    """Return available distributions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


@router.get("/revision/{version}/{target}/{subtarget}")
def api_v1_revision(version: str, target: str, subtarget: str):
    return {
        "revision": get_redis_client().get(f"revision:{version}:{target}/{subtarget}")
    }


@router.get("/latest")
def api_latest():
    return RedirectResponse("/json/v1/latest.json", status_code=301)


@router.get("/overview")
def api_v1_overview():
    return RedirectResponse("/json/v1/overview.json", status_code=301)


def validation_failure(detail: str) -> tuple[dict, int]:
    logging.info(f"Validation failure {detail = }")
    return {"detail": detail, "status": 400}, 400


def validate_request(build_request: BuildRequest) -> tuple[dict, int]:
    """Validate an image request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version and package.

    Args:
        req (dict): The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """

    if build_request.defaults and not settings.allow_defaults:
        return validation_failure("Handling `defaults` not enabled on server")

    if build_request.distro not in get_distros():
        return validation_failure(f"Unsupported distro: {build_request.distro}")

    branch = get_branch(build_request.version)["name"]

    r = get_redis_client()

    if not r.sismember("branches", branch):
        return validation_failure(f"Unsupported branch: {build_request.version}")

    if not r.sismember(f"versions:{branch}", build_request.version):
        return validation_failure(f"Unsupported version: {build_request.version}")

    build_request.packages: list[str] = [
        x.removeprefix("+")
        for x in (build_request.packages_versions.keys() or build_request.packages)
    ]

    logging.debug(f"Profile before mapping {build_request.profile = }")

    if not r.hexists(f"targets:{branch}", build_request.target):
        return validation_failure(f"Unsupported target: {build_request.target}")

    sanitized_profile = build_request.profile.replace(",", "_")
    target_key = f"{branch}:{build_request.version}:{build_request.target}"
    profiles_key = f"profiles:{target_key}"
    if r.sismember(profiles_key, sanitized_profile):
        logging.debug(f"Using {sanitized_profile = }")
        build_request.profile = sanitized_profile
    else:
        mapped_profile = r.hget(f"mapping:{target_key}", build_request.profile)
        logging.debug(f"Checking {mapped_profile = }")
        if mapped_profile:
            build_request.profile = mapped_profile
        elif r.scard(profiles_key) == 1 and r.sismember(profiles_key, "generic"):
            # Assume "generic" as that's the only choice possible.
            # Handles the x86, armsr and other generic variants.
            logging.info(f"Use generic profile replacing {build_request.profile = }")
            build_request.profile = "generic"
        else:
            return validation_failure(f"Unsupported profile: {build_request.profile}")

    return ({}, None)


def return_job_v1(job: Job) -> tuple[dict, int, dict]:
    response: dict = job.get_meta()
    imagebuilder_status: str = "done"
    queue_position: int = 0

    if job.meta:
        response.update(job.meta)

    if job.is_failed:
        response.update(status=500, error=job.latest_result().exc_string)
        imagebuilder_status = "failed"

    elif job.is_queued:
        queue_position = job.get_position() or 0
        response.update(status=202, detail="queued", queue_position=queue_position)
        imagebuilder_status = "queued"

    elif job.is_started:
        response.update(status=202, detail="started")
        imagebuilder_status = response.get("imagebuilder_status", "init")

    elif job.is_finished:
        response.update(status=200, **job.return_value())
        imagebuilder_status = "done"

    headers = {
        "X-Imagebuilder-Status": imagebuilder_status,
        "X-Queue-Position": str(queue_position),
    }

    response.update(enqueued_at=job.enqueued_at, request_hash=job.id)

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


@router.head("/build/{request_hash}")
@router.get("/build/{request_hash}")
def api_v1_build_get(request_hash: str, response: Response) -> dict:
    job: Job = get_queue().fetch_job(request_hash)
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
    request_hash: str = get_request_hash(build_request)
    job: Job = get_queue().fetch_job(request_hash)
    status: int = 200
    result_ttl: str = "7d"
    if build_request.defaults:
        result_ttl = "1h"
    failure_ttl: str = "12h"

    if build_request.client:
        client = build_request.client
    elif user_agent.startswith("auc"):
        client = user_agent.replace(" (", "/").replace(")", "")
    else:
        client = "unknown/0"

    add_timestamp(
        f"stats:clients:{client}",
        {"stats": "clients", "client": client},
    )

    if job is None:
        add_timestamp("stats:cache-misses", {"stats": "cache-misses"})

        content, status = validate_request(build_request)
        if content:
            response.status_code = status
            return content

        job = get_queue().enqueue(
            build,
            build_request,
            job_id=request_hash,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
            job_timeout="10m",
        )
    else:
        if job.is_finished:
            add_timestamp("stats:cache-hits", {"stats": "cache-hits"})

    content, status, headers = return_job_v1(job)
    response.headers.update(headers)
    response.status_code = status

    return content


@router.get("/stats")
def api_v1_builder_stats():
    """Return status of builders

    Returns:
        queue_length: Number of jobs currently in build queue
    """
    return {
        "queue_length": len(get_queue()),
    }
