from http import HTTPStatus
import json

from asu.request import Request
from asu.utils.common import get_hash


class UpgradeCheck(Request):
    """Handle upgrade requests"""

    sysupgrade_requested = True
    required_params = ["distro", "version", "target", "revision", "board_name"]

    def __init__(self, config, db):
        super().__init__(config, db)

    def _process_request(self):
        if self.config.snapshot(self.request["distro"], self.request["version"]):
            revision = self.database.get_revision(
                self.request["distro"], self.request["version"], self.request["target"]
            )
            if self.request_json.get("revision") != revision:
                self.response_json["revision"] = revision
                self.response_json["version"] = self.request["version"]
        else:
            latest_version = self.config.latest(self.request["distro"])
            if latest_version != self.request["version"]:
                self.response_json["version"] = latest_version
            else:
                self.response_status = HTTPStatus.NO_CONTENT  # 204

        if "installed" not in self.request_json:
            return self.respond()
        else:
            bad_request = self.check_bad_packages(self.request_json["installed"].keys())
            if bad_request:
                return bad_request

        self.outdated_version = self.request["version"]
        self.request["version"] = self.request_json["version"]

        # check if packages exists in new version
        bad_request = self.check_bad_packages(self.request_json["installed"].keys())
        if bad_request:
            return bad_request

        # if a version jump happens make sure to check for package changes,
        # drops & renames
        if "version" in self.response_json:
            # this version transforms packages, e.g. kmod-ipv6 was dropped at
            # in the 17.01 release as it became part of the kernel. this
            # functions checks for these changes and tell the client what
            # packages to request in the build request
            self.response_json["packages"] = self.database.transform_packages(
                self.request["distro"],
                self.outdated_version,
                self.request["version"],
                " ".join(self.request_json["installed"].keys()),
            )
            self.response_status = HTTPStatus.OK  # 200
        else:
            self.response_json["packages"] = list(self.request_json["installed"].keys())
            self.response_status = HTTPStatus.NO_CONTENT  # 204

        manifest_content = ""
        for package, version in sorted(self.request_json["installed"].items()):
            manifest_content += "{} - {}\n".format(package, version)
        self.request["manifest_hash"] = get_hash(manifest_content, 15)

        self.request["manifest"] = self.request_json["installed"]

        if "version" in self.response_json or "upgrade_packages" in self.request_json:
            # TODO this result in double jsonifying
            # problem is postgres gives back perfect json while the rest of the
            # json response is a dict, until it's decoded in the end
            self.response_json["upgrades"] = json.loads(
                self.database.get_manifest_upgrades(self.request)
            )
            if self.response_json["upgrades"] != {}:
                self.response_status = HTTPStatus.OK  # 200

        # finally respond
        return self.respond()
