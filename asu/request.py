from http import HTTPStatus
import logging
import json
from flask import Response


class Request:
    """Parent request class"""

    log = logging.getLogger(__name__)
    required_params = ["distro", "version", "target"]
    sysupgrade_requested = False

    def __init__(self, config, database):
        self.config = config
        self.database = database

    def process_request(self, request_json):
        self.request = {}
        self.request_json = request_json
        self.response_json = {}
        self.response_header = {}
        self.response_status = 0

        # check if valid request if no request_hash attached
        if "request_hash" not in self.request_json:
            # first check if all requred params are available
            bad_request = self.check_required_params()
            if bad_request:
                return bad_request

            bad_request = self.check_bad_distro()
            if bad_request:
                return bad_request
            self.log.debug("passed distro check")

            bad_request = self.check_bad_version()
            if bad_request:
                return bad_request
            self.log.debug("passed version check")

            bad_request = self.check_bad_target()
            if bad_request:
                return bad_request
            self.log.debug("passed target check")

            if "profile" in self.request_json:
                bad_request = self.check_bad_profile()
                if bad_request:
                    return bad_request
                self.log.debug("passed profile check")
            else:
                bad_request = self.check_bad_board_name()
                if bad_request:
                    return bad_request
                self.log.debug("passed board_name check")

        return self._process_request()

    def _process_request(self):
        pass

    def check_bad_profile(self):
        self.request["profile"] = self.request_json["profile"]
        if not self.database.check_profile(self.request):
            self.response_json["error"] = "unknown profile {}".format(
                self.request["profile"]
            )
            self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
            return self.respond()

    def check_bad_board_name(self):
        if self.request["target"].startswith("x86"):
            self.request["profile"] = "Generic"
        else:
            self.request["profile"], metadata = self.database.check_board_name(
                self.request, self.request_json["board_name"]
            )
            if not self.request["profile"]:
                self.response_json["error"] = "unknown device {}".format(
                    self.request_json["board_name"]
                )
                self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
                return self.respond()

            if self.sysupgrade_requested and not metadata:
                self.response_json["error"] = "device does not support sysupgrades"
                self.response_status = HTTPStatus.NOT_IMPLEMENTED  # 501
                return self.respond()

    # these checks are relevant for upgrade and image reuqest
    def check_bad_distro(self):
        if not self.request_json["distro"].lower() in self.config.get_distros():
            self.response_json["error"] = "unknown distribution {}".format(
                self.request_json["distro"]
            )
            self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
            return self.respond()
        else:
            self.request["distro"] = self.request_json["distro"].lower()
            return False

    def check_bad_version(self):
        self.request_json["version"] = self.request_json["version"].lower()
        if not self.request_json["version"] in self.config.get(
            self.request["distro"]
        ).get("versions"):
            self.response_json["error"] = "unknown version {}".format(
                self.request_json["version"]
            )
            self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
            return self.respond()
        else:
            self.request["version"] = self.request_json["version"]
            return False

    def check_bad_target(self):
        self.request["target"] = self.request_json["target"]
        if not self.database.check_target(self.request):
            self.response_json["error"] = "unknown target {}".format(
                self.request["target"]
            )
            self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
            return self.respond()
        return False

    def respond(self, json_content=False):
        response = Response(
            response=(
                self.response_json if json_content else json.dumps(self.response_json)
            ),
            status=self.response_status,
            mimetype="application/json",
        )
        response.headers.extend(self.response_header)
        return response

    # check packages by sending requested packages again postgres
    def check_bad_packages(self, packages):
        # remove packages which doesn't exists but appear in the package list
        # upgrade_checks send a dict with package name & version while build
        # requests contain only an array
        packages_set = set(packages) - set(["libc", "kernel", "libgcc", "libgcc1"])

        self.request["packages"] = sorted(list(packages_set))
        packages_unknown = self.database.check_packages(self.request)

        # if list is not empty there where some unknown packages found
        if packages_unknown:
            logging.warning("could not find packages %s", packages_unknown)
            self.response_header["X-Unknown-Package"] = ", ".join(packages_unknown)
            self.response_json["error"] = "could not find packages: {}".format(
                ", ".join(packages_unknown)
            )
            self.response_status = HTTPStatus.UNPROCESSABLE_ENTITY  # 422
            return self.respond()

        # all checks passed, not bad
        return False

    def check_required_params(self):
        for required_param in self.required_params:
            if required_param not in self.request_json:
                self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
                self.response_header["X-Missing-Param"] = required_param
                self.response_json["error"] = "missing parameter: {}".format(
                    required_param
                )
                return self.respond()
