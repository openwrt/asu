"""
Package selection API router.

This router provides endpoints for package selection and validation,
allowing clients to determine the correct package set for a device
without triggering a build.
"""

import logging
from typing import Union

from fastapi import APIRouter, Request, Response

from asu.build_request import BuildRequest
from asu.config import settings
from asu.package_changes import apply_package_changes
from asu.package_selection import get_package_list
from asu.util import (
    client_get,
    get_branch,
    reload_profiles,
    reload_targets,
    reload_versions,
)

router = APIRouter()


def validation_failure(detail: str) -> tuple[dict[str, Union[str, int]], int]:
    logging.info(f"Validation failure {detail = }")
    return {"detail": detail, "status": 400}, 400


def get_distros() -> list:
    """Return available distributions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


def validate_request_basic(
    app,
    build_request: BuildRequest,
) -> tuple[dict[str, Union[str, int]], int]:
    """Validate basic request parameters (distro, version, target, profile)

    This is a lighter validation that doesn't require fetching default packages.
    Used by the package selection API.

    Args:
        app: The FastAPI app instance
        build_request: The image request

    Returns:
        (dict, int): Status message and code, empty if no error appears
    """

    if build_request.distro not in get_distros():
        return validation_failure(f"Unsupported distro: {build_request.distro}")

    branch = get_branch(build_request.version)["name"]

    if branch not in settings.branches:
        return validation_failure(f"Unsupported branch: {build_request.version}")

    if build_request.version not in app.versions:
        reload_versions(app)
        if build_request.version not in app.versions:
            return validation_failure(f"Unsupported version: {build_request.version}")

    if build_request.target not in app.targets[build_request.version]:
        reload_targets(app, build_request.version)
        if build_request.target not in app.targets[build_request.version]:
            return validation_failure(
                f"Unsupported target: {build_request.target}. The requested "
                "target was either dropped, is still being built or is not "
                "supported by the selected version. Please check the forums or "
                "try again later."
            )

    def valid_profile(profile: str, build_request: BuildRequest) -> bool:
        profiles = app.profiles[build_request.version][build_request.target]
        if profile in profiles:
            return True
        if len(profiles) == 1 and "generic" in profiles:
            # Handles the x86, armsr and other generic variants.
            build_request.profile = "generic"
            return True
        return False

    if not valid_profile(build_request.profile, build_request):
        reload_profiles(app, build_request.version, build_request.target)
        if not valid_profile(build_request.profile, build_request):
            return validation_failure(
                f"Unsupported profile: {build_request.profile}. The requested "
                "profile was either dropped or never existed. Please check the "
                "forums for more information."
            )

    build_request.profile = app.profiles[build_request.version][build_request.target][
        build_request.profile
    ]
    return ({}, None)


@router.post("/select")
def api_v1_packages_select(
    build_request: BuildRequest,
    response: Response,
    request: Request,
):
    """
    Determine the package selection for a device.

    This endpoint applies version and target-specific package changes
    to determine what packages should be installed on a device.
    It does not trigger a build.

    Returns the adjusted package list with all necessary modifications applied.
    """
    # Sanitize the profile in case the client did not
    build_request.profile = build_request.profile.replace(",", "_")

    # Validate basic request parameters
    content, status = validate_request_basic(request.app, build_request)
    if content:
        response.status_code = status
        return content

    # Get normalized package list
    build_request.packages = get_package_list(build_request)

    # Apply package changes (version/target specific modifications)
    apply_package_changes(build_request)

    # Return the modified request showing what packages will be used
    return {
        "status": 200,
        "detail": "Package selection completed",
        "packages": build_request.packages,
        "profile": build_request.profile,
        "version": build_request.version,
        "target": build_request.target,
    }


@router.post("/validate")
def api_v1_packages_validate(
    build_request: BuildRequest,
    response: Response,
    request: Request,
):
    """
    Validate a package selection without building.

    This is similar to /select but performs additional validation
    to ensure the request is valid for building.

    Returns validation status and any errors found.
    """
    # Sanitize the profile
    build_request.profile = build_request.profile.replace(",", "_")

    # Validate request
    content, status = validate_request_basic(request.app, build_request)
    if content:
        response.status_code = status
        return content

    if build_request.defaults and not settings.allow_defaults:
        response.status_code = 400
        return {"detail": "Handling `defaults` not enabled on server", "status": 400}

    # Get normalized package list
    build_request.packages = get_package_list(build_request)

    # Apply package changes
    apply_package_changes(build_request)

    return {
        "status": 200,
        "detail": "Request is valid",
        "packages": build_request.packages,
        "profile": build_request.profile,
        "version": build_request.version,
        "target": build_request.target,
    }
