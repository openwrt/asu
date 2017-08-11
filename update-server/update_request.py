from request import Request
from util import get_latest_release
from http import HTTPStatus
import logging

class UpdateRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.log = logging.getLogger(__name__)
        self.needed_values = ["distro", "version", "target", "subtarget"]

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.latest_release = get_latest_release(self.distro)
        if self.release  == "snapshot":
            self.response_dict["version"] = "SNAPSHOT"
            return self.respond(), HTTPStatus.OK
        elif not self.release_latest(self.latest_release, self.release):
            self.response_dict["version"] = self.latest_release
            return self.respond(), HTTPStatus.OK

        if "packages" in self.request_json:
            # perform package transformation
            response = self.database.packages_updates(self.distro, self.release, self.target, self.subtarget, self.request_json["packages"])
            if response:
                self.response_dict["packages"] = {}
                for name, version, version_installed in response:
                    self.response_dict["packages"][name] = [version, version_installed]

                return self.respond(), HTTPStatus.OK

        return("", HTTPStatus.NO_CONTENT)
