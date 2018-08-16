from http import HTTPStatus
import logging

from request import Request
from utils.common import get_hash

class UpgradeCheck(Request):
    def __init__(self, config, db):
        super().__init__(config, db)
        self.log = logging.getLogger(__name__)

    # check if requested version is a snapshot
    # TODO check revision for snapshots to not continiously upgrade them
    # implement this on client side
    def distro_latest_version(self):
        if self.config.version(self.request["distro"], self.request["version"]).get("snapshot", False):
            self.response_json["version"] = self.request_json["version"]
        else:
            self.request["version"] = self.config.get(self.request["distro"]).get("latest")
            if not self.request["version"] == self.installed_version:
                self.response_json["version"] = self.request["version"]

    def _process_request(self):
        # required params for a build request
        missing_params = self.check_missing_params(["distro", "version", "target", "subtarget"])
        if missing_params:
            return self.respond()

        # recreate manifest based on requested packages
        manifest_content = ""
        for package, version in sorted(self.request_json["packages"].items()):
            manifest_content += "{} - {}\n".format(package, version)

        self.request["manifest_hash"] = get_hash(manifest_content, 15)

        # distro version target subtarget profile manifest_hash
        upgrade_check_hash_array = [
                self.request_json["distro"],
                self.request_json["version"],
                self.request_json["target"],
                self.request_json["subtarget"],
                self.request["manifest_hash"]
                ]

        # create hash of the upgrade check
        self.request["check_hash"] = get_hash(" ".join(upgrade_check_hash_array), 15)

        # check database for cached upgrade check
        upgrade_check = self.database.check_upgrade_check_hash(self.request["check_hash"])
        if upgrade_check:
            self.request = upgrade_check

            # check latest version for request
            self.distro_latest_version()

            if self.request["upgrades"]:
                # set upgrade json created by postgresql
                self.response_json["upgrades"] = self.request["upgrades"]

            # instantly respond
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
        self.distro_latest_version()

        # check if target/sutarget still exists in new version
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        # check if packages exists in new version
        bad_packages = self.check_bad_packages()
        if bad_packages:
            return bad_packages

        # package are vaild so safe the clients combination as a manifest
        # TODO this is confusing as request_json[packages] contains package
        # names + version while the validated packages of request[packages] only
        # contain the names...
        self.database.add_manifest_packages(self.image.params["manifest_hash"], self.request_json["packages"])

        # only check for package upgrades if activle requested by the client or version jump
        if "upgrade_packages" in self.request_json or "version" in self.response_json:
            # let postgres create a json dict containing outdated packages
            package_upgrades = self.database.manifest_outdated(self.request)
            if package_upgrades:
                self.response_json["upgrades"] = {}
                for name, current, outdated in package_upgrades:
                    # the "upgrades" should be visually displayed to the client
                    # so save bandwidth the format is simply
                    # { "package_name": [ "new_version", "old_version" ], ... }
                    self.response_json["upgrades"][name] = [ current, outdated ]

        # if a version jump happens make sure to check for package changes, drops & renames
        if "version" in self.request_json:
            # this version transforms packages, e.g. kmod-ipv6 was dropped at in
            # the 17.01 release as it became part of the kernel. this functions
            # checks for these changes and tell the client what packages to
            # request in the build request
            self.response_json["packages"] = [package[0] for package in self.database.transform_packages(
                self.request["distro"], self.installed_version, self.request["version"],
                " ".join(self.request_json["packages"].keys()))]
        else:
            self.request_json["packages"] = self.request["packages"]

        # only if version or upgrades in response something is actually upgraded
        if "version" in self.response_json or "upgrades" in self.response_json:
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        # store request to be able to respond faster on another request without
        # validating all it again
        self.database.insert_upgrade_check(self.request)

        # finally respond
        return self.respond()
