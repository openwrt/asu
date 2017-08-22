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
        packages_transformed = self.packages_transformed = [package[0] for package in self.database.transform_packages(distro, release, self.release, " ".join(packages))]
        self.log.debug("transformed packages {}".format(self.packages_transformed))
        return packages_transformed

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.installed_release = self.release
        self.release = get_latest_release(self.distro)

        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        if self.installed_release  == "snapshot":
            self.response_dict["version"] = "SNAPSHOT"
        elif not self.release == self.installed_release:
            self.response_dict["version"] = self.release

        if "packages" in self.request_json:
            self.packages_installed = self.request_json["packages"]
            if "version" in self.response_dict:
                self.packages_transformed = self.package_transformation(self.distro, self.installed_release, self.packages_installed)
                self.response_dict["packages"] = self.packages_transformed
                self.log.warning(self.response_dict["packages"])

            elif "update_packages" in self.request_json:
                packages_updates = self.database.packages_updates(self.distro, self.release, self.target, self.subtarget, self.packages_installed)
                if packages_updates:
                    self.response_dict["updates"] = {}
                    for name, version, version_installed in packages_updates:
                        self.response_dict["updates"][name] = [version, version_installed]

                self.response_dict["packages"] = self.packages_installed
                self.log.warning(self.response_dict["packages"])

        if "version" in self.response_dict or "packages" in self.response_dict:
            return(self.respond(), HTTPStatus.OK)
        else:
            return("", HTTPStatus.NO_CONTENT)
