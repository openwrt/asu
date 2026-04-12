import re
from typing import Any, Union
from urllib.parse import urlparse

from rq.utils import parse_timeout

from asu.build_request import BuildRequest
from asu.config import settings
from asu.util import is_snapshot_build, report_error, run_cmd


def is_repo_allowed(repo_url: str, allow_list: list[str]) -> bool:
    """Check if a repository URL is allowed by the allow list.

    Uses proper URL parsing to prevent subdomain and userinfo bypasses
    that affect naive prefix matching.
    """
    if not allow_list:
        return False
    parsed = urlparse(repo_url)
    for allowed in allow_list:
        allowed_parsed = urlparse(allowed)
        if (
            parsed.scheme == allowed_parsed.scheme
            and parsed.hostname == allowed_parsed.hostname
            and parsed.path.startswith(allowed_parsed.path.rstrip("/") + "/")
        ):
            return True
    return False


def merge_repositories_conf(base_content: str, extra_repos: dict[str, str]) -> str:
    """
    Merge extra `src/gz <name> <url>` entries into an existing
    `repositories.conf` while preserving all other upstream settings.

    If `base_content` already contains an entry for a repo `name`, that line
    is replaced (by removing the old `src/gz <name> ...` line and appending
    the new one).
    """
    merged = base_content or ""

    # Replace any `src/gz <name> ...` lines already present in the base.
    for name in sorted(extra_repos.keys()):
        merged = re.sub(
            rf"(?m)^src/gz\s+{re.escape(name)}\s+\S+.*\n?",
            "",
            merged,
        )

    merged = merged.rstrip("\n")

    # Append all user requested repos deterministically.
    if extra_repos:
        merged += "\n# extra repositories (asu)\n"
        merged += "\n".join(
            f"src/gz {name} {extra_repos[name]}" for name in sorted(extra_repos)
        )

    # Keep required imagebuilder feed/signature lines even if the base image
    # differs from what we expect.
    if "src imagebuilder file:packages" not in merged:
        merged += ("\n" if merged else "") + "src imagebuilder file:packages"
    if "option check_signature" not in merged:
        merged += ("\n" if merged else "") + "option check_signature"

    return merged.rstrip("\n") + "\n"


def is_apk_build(version: str) -> bool:
    """
    OpenWrt uses apk-style package management starting with 25.12.

    We treat:
    - 25.12.x and newer (including -SNAPSHOT and -rcN) as apk builds
    - anything that does not start with a numeric "X.Y" as non-apk
    """
    match = re.match(r"^(?P<major>\d+)\.(?P<minor>\d+)", version)
    if not match:
        return False
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    return major > 25 or (major == 25 and minor >= 12)


def normalize_apk_repo_url(repo_url: str) -> str:
    """Ensure the OpenWrt apk repo URL ends with `/packages.adb`."""
    url = repo_url.rstrip("/")
    if not url.endswith("/packages.adb"):
        url += "/packages.adb"
    return url


def merge_apk_repositories(base_content: str, extra_urls: list[str]) -> str:
    """
    Merge extra repository URLs into an existing apk-style `repositories`
    file.

    The file contains only URLs (one per line). We append normalized URLs that
    are not already present.
    """
    base_lines = [line.strip() for line in base_content.splitlines() if line.strip()]
    existing = set(base_lines)

    merged_lines = list(base_lines)
    for raw_url in extra_urls:
        url = normalize_apk_repo_url(raw_url)
        if url in existing:
            continue
        merged_lines.append(url)
        existing.add(url)

    return "\n".join(merged_lines).rstrip("\n") + "\n"


def render_repositories_conf(
    base_content: str, extra_repos: dict[str, str], mode: str
) -> str:
    """Render opkg repositories.conf for append or replace mode."""
    if mode == "replace":
        return merge_repositories_conf("", extra_repos)
    return merge_repositories_conf(base_content, extra_repos)


def render_apk_repositories(base_content: str, extra_urls: list[str], mode: str) -> str:
    """Render apk repositories file for append or replace mode."""
    if mode == "replace":
        return merge_apk_repositories("", extra_urls)
    return merge_apk_repositories(base_content, extra_urls)


def read_base_repositories_conf(
    podman: Any,
    image: str,
    build_request: BuildRequest,
    job: Any,
    mounts: list[dict[str, Union[str, bool]]],
    environment: dict[str, str],
    container_repositories_path: str = "/builder/repositories.conf",
) -> str:
    """
    Read the default ImageBuilder repositories files from the base container.

    For SNAPSHOT builds we need to run setup.sh first, since the repositories
    layout is not pre-populated in that case.
    """
    tmp_container = podman.containers.create(
        image,
        command=["sleep", str(parse_timeout(settings.job_timeout))],
        mounts=mounts,
        cap_drop=["all"],
        no_new_privileges=True,
        privileged=False,
        network_mode=settings.container_network_mode,
        auto_remove=True,
        environment=environment,
    )
    tmp_container.start()
    try:
        if is_snapshot_build(build_request.version):
            returncode, _, _ = run_cmd(tmp_container, ["sh", "setup.sh"])
            if returncode:
                report_error(
                    job,
                    f"Could not set up ImageBuilder ({returncode=})",
                )

        returncode, base_repositories_conf, _ = run_cmd(
            tmp_container,
            ["sh", "-c", f"cat {container_repositories_path!r}"],
        )
        if returncode:
            report_error(
                job,
                f"Could not read {container_repositories_path} ({returncode=})",
            )

        return base_repositories_conf
    finally:
        tmp_container.kill()
