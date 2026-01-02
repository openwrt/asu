"""
Package selection logic for OpenWrt firmware builds.

This module contains functions for determining the correct package selection
for a device, including applying package changes and validating packages.
"""

import logging

from asu.build_request import BuildRequest
from asu.package_changes import apply_package_changes
from asu.util import diff_packages

log = logging.getLogger("rq.worker")


def select_packages(
    build_request: BuildRequest,
    default_packages: set[str],
    profile_packages: set[str],
) -> list[str]:
    """
    Determine the final package list for a build request.

    This function applies package changes based on version and target,
    then optionally diffs packages if diff_packages is enabled.

    Args:
        build_request: The build request containing package specifications
        default_packages: Set of default packages from ImageBuilder
        profile_packages: Set of profile-specific packages

    Returns:
        List of packages to be passed to the build command
    """
    # Apply version/target-specific package changes
    apply_package_changes(build_request)

    build_cmd_packages = build_request.packages

    # If diff_packages is enabled, compute the difference
    if build_request.diff_packages:
        build_cmd_packages = diff_packages(
            build_request.packages, default_packages | profile_packages
        )
        log.debug(f"Diffed packages: {build_cmd_packages}")

    return build_cmd_packages


def get_package_list(build_request: BuildRequest) -> list[str]:
    """
    Get the normalized package list from a build request.

    Handles both packages and packages_versions, removing '+' prefix.

    Args:
        build_request: The build request

    Returns:
        List of package names
    """
    packages = [
        x.removeprefix("+")
        for x in (build_request.packages_versions.keys() or build_request.packages)
    ]
    return packages
