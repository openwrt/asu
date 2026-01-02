import logging
from typing import Optional

from fastapi import APIRouter, Request, Response

from asu.build_request import BuildRequest
from asu.package_changes import apply_package_changes
from asu.config import settings
from asu.util import (
    client_get,
    diff_packages,
    get_branch,
    reload_profiles,
    reload_targets,
    reload_versions,
)

router = APIRouter()


class PackageSelectionRequest(BuildRequest):
    """Request model for package selection - same as BuildRequest"""

    pass


def get_distros() -> list:
    """Return available distributions

    Returns:
        list: Available distributions
    """
    return ["openwrt"]


def validation_failure(detail: str) -> tuple[dict[str, str | int], int]:
    logging.info(f"Validation failure {detail = }")
    return {"detail": detail, "status": 400}, 400


def validate_package_request(
    app,
    package_request: PackageSelectionRequest,
) -> tuple[dict[str, str | int], Optional[int]]:
    """Validate a package selection request and return found errors with status code

    Instead of building every request it is first validated. This checks for
    existence of requested profile, distro, version.

    Args:
        app: FastAPI application instance
        package_request: The package selection request

    Returns:
        (dict, int): Status message and code, empty if no error appears

    """

    if package_request.defaults and not settings.allow_defaults:
        return validation_failure("Handling `defaults` not enabled on server")

    if package_request.distro not in get_distros():
        return validation_failure(f"Unsupported distro: {package_request.distro}")

    branch = get_branch(package_request.version)["name"]

    if branch not in settings.branches:
        return validation_failure(f"Unsupported branch: {package_request.version}")

    if package_request.version not in app.versions:
        reload_versions(app)
        if package_request.version not in app.versions:
            return validation_failure(f"Unsupported version: {package_request.version}")

    package_request.packages: list[str] = [
        x.removeprefix("+")
        for x in (package_request.packages_versions.keys() or package_request.packages)
    ]

    if package_request.target not in app.targets[package_request.version]:
        reload_targets(app, package_request.version)
        if package_request.target not in app.targets[package_request.version]:
            return validation_failure(
                f"Unsupported target: {package_request.target}. The requested "
                "target was either dropped, is still being built or is not "
                "supported by the selected version. Please check the forums or "
                "try again later."
            )

    def valid_profile(profile: str, package_request: PackageSelectionRequest) -> bool:
        profiles = app.profiles[package_request.version][package_request.target]
        if profile in profiles:
            return True
        if len(profiles) == 1 and "generic" in profiles:
            # Handles the x86, armsr and other generic variants.
            package_request.profile = "generic"
            return True
        return False

    if not valid_profile(package_request.profile, package_request):
        reload_profiles(app, package_request.version, package_request.target)
        if not valid_profile(package_request.profile, package_request):
            return validation_failure(
                f"Unsupported profile: {package_request.profile}. The requested "
                "profile was either dropped or never existed. Please check the "
                "forums for more information."
            )

    package_request.profile = app.profiles[package_request.version][
        package_request.target
    ][package_request.profile]
    return ({}, None)


def get_profile_packages(
    version: str, target: str, profile: str
) -> tuple[set[str], set[str]]:
    """Get default and profile packages for a specific configuration

    Args:
        version: OpenWrt version
        target: Target architecture
        profile: Device profile

    Returns:
        tuple: (default_packages, profile_packages)
    """
    branch_data = get_branch(version)
    version_path = branch_data["path"].format(version=version)
    req = client_get(
        settings.upstream_url + f"/{version_path}/targets/{target}/profiles.json"
    )

    if req.status_code != 200:
        return set(), set()

    profiles_data = req.json()
    default_packages = set(profiles_data.get("default_packages", []))

    if profile in profiles_data.get("profiles", {}):
        profile_packages = set(profiles_data["profiles"][profile].get("packages", []))
    else:
        profile_packages = set()

    return default_packages, profile_packages


@router.post("/packages")
def api_v1_packages(
    package_request: PackageSelectionRequest,
    response: Response,
    request: Request,
):
    """Determine package selection for a device without building

    This endpoint validates the request and returns the final package list
    that would be used for building, including:
    - Applied package changes (version-specific adjustments)
    - Diff packages calculation if requested
    - Default and profile packages

    This allows clients to:
    1. Preview what packages will be installed
    2. Validate package selections before requesting a build
    3. Run as a separate service for package determination
    """
    # Sanitize the profile in case the client did not
    package_request.profile = package_request.profile.replace(",", "_")

    content, status = validate_package_request(request.app, package_request)
    if content:
        response.status_code = status
        return content

    # Get default and profile packages
    default_packages, profile_packages = get_profile_packages(
        package_request.version, package_request.target, package_request.profile
    )

    # Apply version/target/profile specific package changes
    apply_package_changes(package_request)

    # Calculate final package list
    build_cmd_packages = package_request.packages

    if package_request.diff_packages:
        build_cmd_packages = diff_packages(
            package_request.packages, default_packages | profile_packages
        )

    return {
        "status": 200,
        "detail": "Package selection completed",
        "packages": build_cmd_packages,
        "default_packages": sorted(default_packages),
        "profile_packages": sorted(profile_packages),
        "requested_packages": package_request.packages,
        "diff_packages": package_request.diff_packages,
        "profile": package_request.profile,
        "version": package_request.version,
        "target": package_request.target,
    }
