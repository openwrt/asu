from http import HTTPStatus
import logging
import json
from flask import Response

class Request():
    def __init__(self, config, database):
        self.config = config
        self.database = database
        self.log = logging.getLogger(__name__)

    def request(self, request_json, sysupgrade=False):
        self.request_json = request_json
        self.response_json = {}
        self.response_header = {}
        self.response_status = 0
        self.sysupgrade = sysupgrade
        return self._request()

    def _request(self):
        pass

    # these checks are relevant for upgrade and image reuqest
    def check_bad_request(self):
        # I'm considering a dict request is faster than asking the database
        self.image["distro"] = self.request_json["distro"].lower()
        if not self.distro in self.config.get_distros():
            self.response_json["error"] = "unknown distribution %s" % self.distro
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()

        # same here
        self.release = self.config.get(self.image["distro"]).get("latest")
        if not self.release in self.config.get(self.image["distro"]).get("releases"): # rename releases to versions
            self.response_json["error"] = "unknown release %s" % self.release
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()

        # all checks passed, not bad
        return False

    def check_bad_target(self):
        self.image["target"] = self.request_json["target"]
        self.image["subtarget"] = self.request_json["subtarget"]

        # check if sysupgrade is supported. If None is returned the subtarget isn't found
        sysupgrade_supported = self.database.sysupgrade_supported(self.image)
        if sysupgrade_supported == None
            self.response_json["error"] = "unknown target %s/%s" % (self.image["target"], self.image["subtarget"])
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()
        elif sysupgrade_supported and self.sysupgrade: 
            self.response_json["error"] = "target currently not supported %s/%s" % (self.image["target"], self.image["subtarget"])
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

    def missing_params(self, params):
        for param in params:
            if not param in self.request_json:
                self.response_header["X-Missing-Param"] = param
                return self.respond()

        # all checks passed, not bad
        return False

    # check packages by sending requested packages again postgres
    def check_bad_packages(self):
        self.image["packages"] = sorted(list(set(self.request_json["packages"])))
        packages_unknown = " ".join(self.database.check_packages(self.image))

        # if list is not empty there where some unknown packages found
        if unknown_packages:
            logging.warning("could not find packages %s", packages_unknown)
            self.response_header["X-Unknown-Package"] = packages_unknown
            self.response_json["error"] = "could not find packages '{}' for requested target".format(packages_unknown)
            self.response_status = HTTPStatus.UNPROCESSABLE_ENTITY # 422
            return self.respond()

        # all checks passed, not bad
        return False
