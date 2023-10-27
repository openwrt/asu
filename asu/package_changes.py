import logging

log = logging.getLogger("rq.worker")


def appy_package_changes(req):
    """
    Apply package changes to the request

    Args:
        req (dict): The image request
        log (logging.Logger): The logger to use
    """

    def _add_if_missing(package):
        if package not in req["packages"]:
            req["packages"].append(package)
            log.debug(f"Added {package} to packages")

    # 23.05 specific changes
    if req["version"].startswith("23.05"):
        # mediatek/mt7622 specific changes
        if req["target"] == "mediatek/mt7622":
            _add_if_missing("kmod-mt7622-firmware")

        # ath79/generic specific changes
        elif req["target"] == "ath79/generic":
            if req["profile"] in {
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

            elif req["profile"] == "buffalo_wzr-hp-g300nh-rb":
                _add_if_missing("kmod-switch-rtl8366rb")
