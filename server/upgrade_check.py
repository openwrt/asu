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
            manifest_content += "{} - {}\n".format(package, version)

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

        # package are vaild so safe the clients combination as a manifest
        self.database.add_manifest_packages(self.image.params["manifest_hash"], manifest_content)

        # only check for package upgrades if activle requested by the client or version jump
        if "upgrade_packages" in self.request_json or "version" in self.response_json:
            # let postgres create a json dict containing outdated packages
            package_upgrades = self.database.manifest_outdated(self.request)
            if package_upgrades:
                self.response_json["upgrades"] = {}
                for name, current, outdated in package_upgrades:
                    # the "upgrades" should be visually displayed to the client
                    self.response_json["upgrades"][package] = [ current, outdated ]

        # if a version jump happens make sure to check for package changes, drops & renames
        if "version" in self.request_json:
            self.response_json["packages"] = [package[0] for package in self.database.transform_packages(
                self.request["distro"], self.installed_version, self.request["version"],
                " ".join(self.request_json["packages"].keys()))]

        # only if version or upgrades in response something is actually upgraded
        if "version" in self.response_json or "upgrades" in self.response_json:
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        return self.respond()
        
