from request import Request
from util import get_latest_release
from http import HTTPStatus
import logging

class UpdateRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.log = logging.getLogger(__name__)
        self.needed_values = ["distro", "version", "target", "subtarget"]

    def package_transformation(self, distro, release, packages):
        # perform package transformation
        # this function is still a dummy
        self.packages_transformed = {}
        if self.packages_transformed:
            self.response_dict["transformations"] = self.packages_transformed
        return packages

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.latest_release = get_latest_release(self.distro)

        if self.release  == "snapshot":
            self.response_dict["version"] = "SNAPSHOT"
        elif not self.release_latest(self.latest_release, self.release):
            self.response_dict["version"] = self.latest_release

        if "packages" in self.request_json:
            self.packages_installed = self.package_transformation(self.distro, self.release, self.request_json["packages"])

            packages_updates = self.database.packages_updates(self.distro, self.release, self.target, self.subtarget, self.packages_installed)
            if packages_updates:
                self.response_dict["updates"] = {}
                for name, version, version_installed in packages_updates:
                    self.response_dict["updates"][name] = [version, version_installed]

            self.response_dict["packages"] = []
            self.response_dict["packages"].extend(list(self.packages_installed.keys()))
            self.response_dict["packages"].extend(list(self.packages_transformed.keys()))
            self.log.warning(self.response_dict["packages"])

        if "version" in self.response_dict or "packages" in self.response_dict:
            return(self.respond(), HTTPStatus.OK)
        else:
            return("", HTTPStatus.NO_CONTENT)
