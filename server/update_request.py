from http import HTTPStatus
import logging
from collections import OrderedDict

from server.request import Request
from utils.common import get_latest_release, get_hash


class UpdateRequest(Request):
    def __init__(self, db):
        super().__init__(db)
        self.log = logging.getLogger(__name__)

    def package_transformation(self, distro, release, packages):
        # perform package transformation
        packages_transformed = self.packages_transformed = [package[0] for package in self.database.transform_packages(distro, release, self.release, " ".join(packages))]
        self.log.debug("transformed packages {}".format(self.packages_transformed))
        return packages_transformed

    def _request(self):
        if "request_hash" in self.request_json:
            check_result = self.database.check_upgrade_request_hash(self.request_json["request_hash"])
            if check_result:
                self.response_json = check_result
            else:
                self.response_status = HTTPStatus.NOT_FOUND

            return self.respond(True)
        else:
            for needed_value in ["distro", "version", "target", "subtarget"]:
                if not needed_value in self.request_json:
                    self.response_status = HTTPStatus.BAD_REQUEST
                    return self.respond()

            bad_request = self.check_bad_request()
            if bad_request:
                return bad_request

            # check target for old version
            bad_target = self.check_bad_target()
            if bad_target:
                return bad_target

            bad_packages = self.check_bad_packages()
            if bad_packages:
                return bad_packages

            self.installed_release = self.release
            if self.installed_release  == "snapshot":
                self.release = "snapshot"
                self.response_json["version"] = "snapshot"
            else:
                self.release = get_latest_release(self.distro)
                if not self.release == self.installed_release:
                    self.response_json["version"] = self.release

            # check target for new version
            bad_target = self.check_bad_target()
            if bad_target:
                return bad_target

            bad_packages = self.check_bad_packages()
            if bad_packages:
                return bad_packages

            if "packages" in self.request_json:
                self.log.debug(self.request_json["packages"])
                self.packages_installed = OrderedDict(sorted(self.request_json["packages"].items()))
                package_versions = {}
                self.response_json["packages"] = OrderedDict()
                if "version" in self.response_json:
                    self.packages_transformed = self.package_transformation(self.distro, self.installed_release, self.packages_installed)
                    package_versions = self.database.packages_versions(self.distro, self.release, self.target, self.subtarget, " ".join(self.packages_transformed))
                else:
                    package_versions = self.database.packages_versions(self.distro, self.release, self.target, self.subtarget, " ".join(self.packages_installed))

                if "upgrade_packages" in self.request_json or "version" in self.response_json:
                    if self.request_json["upgrade_packages"] is 1 or "version" in self.response_json:
                        for package, version in package_versions:
                            self.response_json["packages"][package] = version
                            if package in self.packages_installed.keys():
                                if self.packages_installed[package] != version:
                                    if not "upgrades" in self.response_json:
                                        self.response_json["upgrades"] = {}
                                    self.response_json["upgrades"][package] = [version, self.packages_installed[package]]
                self.response_json["packages"] = OrderedDict(sorted(self.response_json["packages"]))

            if "version" in self.response_json or "upgrades" in self.response_json:
                self.response_status = HTTPStatus.OK # 200
            else:
                self.response_status = HTTPStatus.NO_CONTENT # 204

            self.request_manifest_hash = get_hash(str(self.packages_installed), 15)
            self.database.add_manifest_packages(self.request_manifest_hash, self.packages_installed)

            request_hash = get_hash(" ".join([self.distro, self.release, self.target, self.subtarget, self.request_manifest_hash]), 16)

            if "version" in self.request_json:
                self.response_manifest_hash = get_hash(str(self.response_json["packages"]), 15)
                self.database.add_manifest_packages(self.response_manifest_hash, self.response_json["packages"])
                self.database.insert_upgrade_check(request_hash, self.distro, self.installed_release, self.target, self.subtarget, self.request_manifest_hash, self.release, self.response_manifest_hash)
            else:
                self.database.insert_upgrade_check(request_hash, self.distro, self.installed_release, self.target, self.subtarget, self.request_manifest_hash, self.release, self.request_manifest_hash)

            self.response_json["request_hash"] = request_hash

            return self.respond()
