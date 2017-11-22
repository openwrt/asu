from http import HTTPStatus
import logging
import json
from flask import Response

from utils.config import Config
from utils.database import Database
from utils.common import get_latest_release

class Request():
    def __init__(self, request_json):
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.request_json = request_json
        self.response_json = {}
        self.response_header = {}
        self.response_status = 0
        self.database = Database()
        self.sysupgrade = False

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

    def check_bad_request(self):
        if not "distro" in self.request_json:
            self.distro = "lede"
        else:
            self.distro = self.request_json["distro"].lower()

            if not self.distro in self.config.get("distributions").keys():
                self.log.info("update request unknown distro")
                self.response_json["error"] = "unknown distribution %s" % self.distro
                self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
                return self.respond()

        if not "version" in self.request_json:
            self.release = get_latest_release(self.distro)
        else:
            self.release = self.request_json["version"].lower()

            if not self.release in self.database.get_releases(self.distro):
                self.response_json["error"] = "unknown release %s" % self.release
                self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
                return self.respond()

    def check_bad_target(self):
        self.target = self.request_json["target"]
        self.subtarget = self.request_json["subtarget"]

        subtarget_check =  self.database.get_subtargets(self.distro, self.release, self.target, self.subtarget)
        if not len(subtarget_check) == 1:
            self.response_json["error"] = "unknown target %s/%s" % (self.target, self.subtarget)
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            return self.respond()
        elif not subtarget_check[0][2] == "1" and self.sysupgrade: # [2] is supported flag
            self.response_json["error"] = "target currently not supported %s/%s" % (self.target, self.subtarget)
            self.response_status = HTTPStatus.UNPROCESSABLE_ENTITY # 412
            return self.respond()

        if self.database.subtarget_outdated(self.distro, self.release, self.target, self.subtarget):
            self.log.debug("subtarget %s/%s not outdated - no need to setup imagebuilder", self.target, self.subtarget)
            if not self.database.imagebuilder_status(self.distro, self.release, self.target, self.subtarget) == 'ready':
                self.log.debug("imagebuilder not ready")
                self.response_header["X-Imagebuilder-Status"] = "initialize"
                self.response_status = HTTPStatus.ACCEPTED # 202
                return self.respond()

        return False

    def respond(self):
        response = Response(
                response=json.dumps(self.response_json),
                status=self.response_status)
        response.headers = self.response_header
        return response

    # if local version is newer than received returns true
    def release_latest(self, latest, external):
        return LooseVersion(external) >= LooseVersion(latest)

    def check_bad_packages(self):
        self.packages = None
        if "packages" in self.request_json:
            self.packages = self.request_json["packages"]
            available_packages = self.database.get_packages_available(self.distro, self.release, self.target, self.subtarget).keys()
            for package in self.packages:
                if package in ["kernel", "libc", "base-files"]: # these tend to cause problems, even tho always installed
                    pass # kernel is not an installable package, but installed...
                elif package not in available_packages:
                    logging.warning("could not find package {}/{}/{}/{}/{}".format(self.distro, self.release, self.target, self.subtarget, package))
                    self.response_json["error"] = "could not find package '{}' for requested target".format(package)
                    self.response_status = HTTPStatus.UNPROCESSABLE_ENTITY # 422
                    return self.respond()
        return False
