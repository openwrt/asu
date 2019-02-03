from http import HTTPStatus
import logging

from asu.request import Request
from asu.utils.common import get_hash

class UpgradeCheck(Request):
    def __init__(self, config, db):
        super().__init__(config, db)
        self.log = logging.getLogger(__name__)

    def _process_request(self):
        if not "distro" in self.request_json:
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            self.response_header["X-Missing-Param"] = "distro"
            return self.respond()
        else:
            bad_request = self.check_bad_distro()
            if bad_request: return bad_request

        if not "version" in self.request_json:
            self.response_json["version"] = self.config.get(self.request["distro"]).get("latest")
            return self.respond()
        else:
            bad_request = self.check_bad_version()
            if bad_request: return bad_request
            if self.config.version(self.request["distro"], self.request["version"]).get("snapshot", False):
                self.response_json["version"] = self.request["version"]
            else:
                latest_version = self.config.get(self.request["distro"]).get("latest")
                if latest_version != self.request["version"]:
                    self.response_json["version"] = latest_version
                else:
                    self.response_status = HTTPStatus.NO_CONTENT # 204

        if not ("target" in self.request_json and "subtarget" in self.request_json):
            return self.respond()
        else:
            # check if target/sutarget still exists in new version
            bad_request = self.check_bad_target()
            if bad_request: return bad_request

        if not "installed" in self.request_json:
            return self.respond()
        else:
            bad_request = self.check_bad_packages(self.request_json["installed"].keys())
            if bad_request: return bad_request

        self.outdated_version = self.request["version"]
        self.request["version"] = self.response_json["version"]

        # check if packages exists in new version
        bad_request = self.check_bad_packages(self.request_json["installed"])
        if bad_request: return bad_request


        # if a version jump happens make sure to check for package changes, drops & renames
        if "version" in self.response_json:
            # this version transforms packages, e.g. kmod-ipv6 was dropped at in
            # the 17.01 release as it became part of the kernel. this functions
            # checks for these changes and tell the client what packages to
            # request in the build request
            self.response_json["packages"] = [package[0] for package in self.database.transform_packages(
                self.request["distro"], self.outdated_version, self.request["version"],
                " ".join(self.request_json["installed"].keys()))]
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        # finally respond
        return self.respond()
