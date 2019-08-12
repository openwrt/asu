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

    def process_request(self, request):
        self.request = request
        self.response_json = {}
        self.response_header = {}
        self.response_status = 0

        # check if valid request if no request_hash attached
        if "request_hash" not in self.request:
            if not self.database.check_profile(self.request):
                self.log.warning("bad request %s", self.request)
                self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
                return self.respond()
            else:
                self.log.debug("good request %s", self.request)

        return self._process_request()

    def _process_request(self):
        pass

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
            if required_param not in self.request:
                self.response_status = HTTPStatus.PRECONDITION_FAILED  # 412
                self.response_header["X-Missing-Param"] = required_param
                self.response_json["error"] = "missing parameter: {}".format(
                    required_param
                )
                return self.respond()
