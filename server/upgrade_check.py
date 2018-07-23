from http import HTTPStatus
import logging
from collections import OrderedDict

from server.request import Request
from utils.common import get_hash

class UpgradeCheck(Request):
    def __init__(self, config, db):
        super().__init__(config, db)
        self.log = logging.getLogger(__name__)

    def package_transformation(self, distro, version, packages):
        # perform package transformation
        packages_transformed = self.packages_transformed = [package[0] for package in self.database.transform_packages(distro, version, self.version, " ".join(packages))]
        self.log.debug("transformed packages {}".format(self.packages_transformed))
        return packages_transformed

    def _request(self):
        # required params for a build request
        missing_params = self.check_missing_params(["distro", "version", "target", "subtarget", "profile"])
        if missing_params:
            return self.respond()

        # upgrade_request_hash
        # distro version target subtarget profile manifest_hash

        # recreate manifest based on requested packages
        manifest_content = ""
        for package, version in sorted(self.request_json["packages"].items()):
            manifest_content += "{} {}\n".format(package, version)

        self.request["manifest_hash"] = get_hash(manifest_content, 15)

        upgrade_check_hash_array = [
                self.request["distro"],
                self.request["version"],
                self.request["target"],
                self.request["subtarget"],
                self.request["profile"],
                self.request["manifest_hash"]
                ]

        # create hash of the upgrade check
        upgrade_check_hash = get_hash(" ".join(upgrade_request_hash_array), 15)

        # check database for cached upgrade check
        upgrade_check = self.database.check_upgrade_check_hash(upgrade_check_hash)
        if upgrade_check:
            self.response_json = upgrade_check
            return self.respond()

        # if not perform various checks to see if the request is acutally valid

        # check for valid distro and version/version
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        # check for valid target and subtarget
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        # check for existing packages
        bad_packages = self.check_bad_packages()
        if bad_packages:
            return bad_packages

        self.installed_version = self.request["version"]
        # check if requested version is a snapshot
        # TODO check revision for snapshots to not continiously upgrade them
        # implement this on client side
        if self.config.version(self.request["distro"], self.request["version"]).get("snapshot", False):
            self.response_json["version"] = self.request_json["version"]
        else:
            self.request["version"] = self.config.get(self.distro).get("latest")
            if not self.request["version"] == self.installed_version:
                self.response_json["version"] = self.request["version"]

        # check if target/sutarget still exists in new version
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        # check if packages exists in new version
        bad_packages = self.check_bad_packages()
        if bad_packages:
            return bad_packages

        if "version" in self.response_json or "upgrades" in self.response_json:
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        return self.respond()

        
        # this is obviously crazy
        if "packages" in self.request_json:
            self.packages_installed = OrderedDict(sorted(self.request_json["packages"].items()))
            package_versions = {}
            self.response_json["packages"] = OrderedDict()
            if "version" in self.response_json:
                self.packages_transformed = self.package_transformation(self.distro, self.installed_version, self.packages_installed)
                package_versions = self.database.packages_versions(self.distro, self.version, self.target, self.subtarget, " ".join(self.packages_transformed))
            else:
                package_versions = self.database.packages_versions(self.distro, self.version, self.target, self.subtarget, " ".join(self.packages_installed))

            if not "upgrades" in self.response_json:
                self.response_json["upgrades"] = {}

            if "upgrade_packages" in self.request_json or "version" in self.response_json:
                if self.request_json["upgrade_packages"] is 1 or "version" in self.response_json:
                    for package, version in package_versions:
                        if package and version:
                            self.response_json["packages"][package] = version
                            if package in self.packages_installed.keys():
                                if self.packages_installed[package] != version:
                                    self.response_json["upgrades"][package] = [version, self.packages_installed[package]]

            self.response_json["packages"] = OrderedDict(sorted(self.response_json["packages"].items()))

        if "version" in self.response_json or "upgrades" in self.response_json:
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        self.request_manifest_hash = get_hash(str(self.packages_installed), 15)
        self.database.add_manifest_packages(self.request_manifest_hash, self.packages_installed)

        request_hash = get_hash(" ".join([self.distro, self.version, self.target, self.subtarget, self.request_manifest_hash]), 16)

        if "version" in self.request_json:
            self.response_manifest_hash = get_hash(str(self.response_json["packages"]), 15)
            self.database.add_manifest_packages(self.response_manifest_hash, self.response_json["packages"])
            self.database.insert_upgrade_check(request_hash, self.distro, self.installed_version, self.target, self.subtarget, self.request_manifest_hash, self.version, self.response_manifest_hash)
        else:
            self.database.insert_upgrade_check(request_hash, self.distro, self.installed_version, self.target, self.subtarget, self.request_manifest_hash, self.version, self.request_manifest_hash)

        self.response_json["request_hash"] = request_hash

        return self.respond()
