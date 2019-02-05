from http import HTTPStatus
import logging
import json
from flask import Response

class Request():
    def __init__(self, config, database):
        self.config = config
        self.database = database
        self.log = logging.getLogger(__name__)

    def process_request(self, request_json, sysupgrade_requested=False):
        self.request = {}
        self.request_json = request_json
        self.response_json = {}
        self.response_header = {}
        self.response_status = 0
        self.sysupgrade_requested = sysupgrade_requested
        return self._process_request()

    def _process_request(self):
        pass

    # these checks are relevant for upgrade and image reuqest
    def check_bad_distro(self):
        if not self.request_json["distro"].lower() in self.config.get_distros():
            self.response_json["error"] = "unknown distribution {}".format(self.request_json["distro"])
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()
        else:
            self.request["distro"] =  self.request_json["distro"].lower()
            return False

    def check_bad_version(self):
        if not self.request_json["version"] in self.config.get(self.request["distro"]).get("versions"):
            self.response_json["error"] = "unknown version %s".format(self.request_json["version"])
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()
        else:
            self.request["version"] = self.request_json["version"]
            return False

    def check_bad_target(self):
        self.request["target"] = self.request_json["target"]

        # check if sysupgrade is supported. If None is returned the subtarget isn't found
        sysupgrade_supported = self.database.sysupgrade_supported(self.request)
        if sysupgrade_supported == None:
            self.response_json["error"] = "unknown target {}".format(self.request["target"])
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()
        elif not sysupgrade_supported and self.sysupgrade_requested:
            self.response_json["error"] = "target currently not supported {}".format(self.request["target"])
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()

        # all checks passed, not bad
        return False

    def respond(self, json_content=False):
        response = Response(
                response=(self.response_json if json_content else json.dumps(self.response_json)),
                status=self.response_status,
                mimetype='application/json')
        response.headers.extend(self.response_header)
        return response

    def check_missing_params(self, params):
        for param in params:
            if not param in self.request_json:
                self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
                self.response_header["X-Missing-Param"] = param
                return self.respond()

        # all checks passed, not bad
        return False

    # check packages by sending requested packages again postgres
    def check_bad_packages(self, packages):
        # remove packages which doesn't exists but appear in the package list
        # upgrade_checks send a dict with package name & version while build
        # requests contain only an array
        packages_set = set(packages) - set(["libc", "kernel"])

        self.request["packages"] = sorted(list(packages_set))
        packages_unknown = self.database.check_packages(self.request)

        # if list is not empty there where some unknown packages found
        if packages_unknown:
            logging.warning("could not find packages %s", packages_unknown)
            self.response_header["X-Unknown-Package"] = ", ".join(packages_unknown)
            self.response_json["error"] = \
                    "could not find packages: {}".format(", ".join(packages_unknown))
            self.response_status = HTTPStatus.UNPROCESSABLE_ENTITY # 422
            return self.respond()

        # all checks passed, not bad
        return False
