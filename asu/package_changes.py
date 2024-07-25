import logging

from asu.build_request import BuildRequest

log = logging.getLogger("rq.worker")


def appy_package_changes(build_request: BuildRequest):
    """
    Apply package changes to the request

    Args:
        req (dict): The image request
        log (logging.Logger): The logger to use
    """

    def _add_if_missing(package):
        if package not in build_request.packages:
            build_request.packages.append(package)
            log.debug(f"Added {package} to packages")

    # 23.05 specific changes
    if build_request.version.startswith("23.05"):
        # mediatek/mt7622 specific changes
        if build_request.target == "mediatek/mt7622":
            _add_if_missing("kmod-mt7622-firmware")

        # ath79/generic specific changes
        elif build_request.target == "ath79/generic":
            if build_request.profile in {
                "buffalo_wzr-hp-g300nh-s",
                "dlink_dir-825-b1",
                "netgear_wndr3700",
                "netgear_wndr3700-v2",
                "netgear_wndr3800",
                "netgear_wndr3800ch",
                "netgear_wndrmac-v1",
                "netgear_wndrmac-v2",
                "trendnet_tew-673gru",
            }:
                _add_if_missing("kmod-switch-rtl8366s")

            elif build_request.profile == "buffalo_wzr-hp-g300nh-rb":
                _add_if_missing("kmod-switch-rtl8366rb")
