from http import HTTPStatus
from sys import getsizeof

from asu.utils.image import Image
from asu.utils.common import get_hash, get_packages_hash, get_request_hash
from asu.request import Request

class BuildRequest(Request):
    def __init__(self, config, db):
        super().__init__(config, db)

    def _process_request(self):
        self.log.debug("request_json: %s", self.request_json)

        # if request_hash is available check the database directly
        if "request_hash" in self.request_json:
            self.request = self.database.check_request_hash(
                    self.request_json["request_hash"])

            if not self.request:
                self.response_status = HTTPStatus.NOT_FOUND
                return self.respond()
            else:
                return self.return_status()

        #TODO check for profile or board

        # generic approach for https://github.com/aparcar/attendedsysupgrade-server/issues/91
        self.request_json["board"] = self.request_json["board"].replace(",", "_")

        self.request_json["profile"] = self.request_json["board"] # TODO fix this workaround

        request_hash = get_request_hash(self.request_json)
        request_database = self.database.check_request_hash(request_hash)

        # if found return instantly the status
        if request_database:
            self.log.debug("found image in database: %s", request_database["request_status"])
            self.request = request_database
            return self.return_status()
        else:
            self.request["request_hash"] = request_hash
            self.response_json["request_hash"] = self.request["request_hash"]

        # if not perform various checks to see if the request is acutally valid

        # validate distro and version
        if not "distro" in self.request_json:
            self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
            self.response_header["X-Missing-Param"] = "distro"
            return self.respond()
        else:
            bad_request = self.check_bad_distro()
            if bad_request: return bad_request

        if not "version" in self.request_json:
            self.request["version"] = self.config.get(self.request["distro"]).get("latest")
        else:
            bad_request = self.check_bad_version()
            if bad_request: return bad_request

        # check for valid target
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        # validate attached defaults
        if "defaults" in self.request_json:
            if self.request_json["defaults"]:
                # check if the uci file exceeds the max file size. this should be
                # done as the uci-defaults are at least temporary stored in the
                # database to be passed to a worker
                if getsizeof(self.request_json["defaults"]) > self.config.get(
                        "max_defaults_size", 1024):
                    self.response_json["error"] = "attached defaults exceed max size"
                    self.response_status = 420 # this error code is the best I could find
                    self.respond()
                else:
                    self.request["defaults_hash"] = get_hash(
                            self.request_json["defaults"], 32)
                    self.database.insert_defaults(
                            self.request["defaults_hash"], self.request_json["defaults"])

        # add package_hash to database
        if "packages" in self.request_json:
            # check for existing packages
            bad_packages = self.check_bad_packages(self.request_json["packages"])
            if bad_packages:
                return bad_packages
            self.request["packages_hash"] = get_packages_hash(self.request_json["packages"])
            self.database.insert_packages_hash(
                    self.request["packages_hash"], self.request["packages"])

        # now some heavy guess work is done to figure out the profile
        # eventually this could be simplified if upstream unifirm the profiles/boards
        if "board" in self.request_json:
            self.log.debug("board in request, search for %s", self.request_json["board"])
            self.request["profile"] = self.database.check_profile(
                    self.request["distro"], self.request["version"],
                    self.request["target"], self.request_json["board"])

        if not self.request["profile"]:
            if "model" in self.request_json:
                self.log.debug("model in request, search for %s", self.request_json["model"])
                self.request["profile"] = self.database.check_model(
                        self.request["distro"], self.request["version"],
                        self.request["target"], self.request_json["model"])
                self.log.debug("model search found profile %s", self.request["profile"])

        if not self.request["profile"]:
            if self.database.check_profile(self.request["distro"],
                    self.request["version"], self.request["target"], "Generic"):
                self.request["profile"] = "Generic"
            elif self.database.check_profile(self.request["distro"],
                    self.request["version"], self.request["target"], "generic"):
                self.request["profile"] = "generic"
            else:
                self.response_json["error"] = "unknown device, please check model and board params"
                self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
                return self.respond()

        # all checks passed, eventually add to queue!
        self.log.debug("add build job %s", self.request)
        self.database.add_build_job(self.request)
        return self.return_queued()

    def return_queued(self):
        self.response_header["X-Imagebuilder-Status"] = "queue"
        if "build_position" in self.request:
            self.response_header['X-Build-Queue-Position'] = self.request["build_position"]
        self.response_json["request_hash"] = self.request["request_hash"]

        self.response_status = HTTPStatus.ACCEPTED # 202
        return self.respond()

    def return_status(self):
        # image created, return all desired information
        if self.request["request_status"] == "created":
            image_path = self.database.get_image_path(self.request["image_hash"])
            self.response_json["sysupgrade"] = image_path["sysupgrade"]
            self.response_json["log"] = "/download/{}/buildlog-{}.txt".format(
                    image_path["file_path"], self.request["image_hash"])
            self.response_json["files"] = "/json/{}/".format(image_path["file_path"])
            self.response_json["request_hash"] = self.request["request_hash"]
            self.response_json["image_hash"] = self.request["image_hash"]

            self.response_status = HTTPStatus.OK # 200

        elif self.request["request_status"] == "no_sysupgrade":
            if self.sysupgrade_requested:
                # no sysupgrade found but requested, let user figure out what to do
                self.response_json["error"] = "No sysupgrade file produced, may not supported by model."

                self.response_status = HTTPStatus.NOT_IMPLEMENTED # 501
            else:
                # no sysupgrade found but not requested, factory image is likely from interest
                image_path = self.database.get_image_path(self.request["image_hash"])
                self.response_json["files"] = "/json/{}/".format(image_path["file_path"])
                self.response_json["log"] = "/download/{}/buildlog-{}.txt".format(
                        image_path["file_path"], self.request["image_hash"])
                self.response_json["request_hash"] = self.request["request_hash"]
                self.response_json["image_hash"] = self.request["image_hash"]

                self.response_status = HTTPStatus.OK # 200

            self.respond()

        # image request passed validation and is queued
        elif self.request["request_status"] == "requested":
            self.return_queued()

        # image is currently building
        elif self.request["request_status"] == "building":
            self.response_header["X-Imagebuilder-Status"] = "building"
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = HTTPStatus.ACCEPTED # 202

        # build failed, see build log for details
        elif self.request["request_status"] == "build_fail":
            self.response_json["error"] = "ImageBuilder faild to create image"
            self.response_json["log"] = "/download/faillogs/faillog-{}.txt".format(
                    self.request["request_hash"])
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR # 500

        # likely to many package where requested
        elif self.request["request_status"] == "imagesize_fail":
            self.response_json["error"] = \
                    "No firmware created due to image size. Try again with less packages selected."
            self.response_json["log"] = \
                    "/download/faillogs/faillog-{}.txt".format(self.request["request_hash"])
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = 413 # PAYLOAD_TO_LARGE RCF 7231

        # something happend with is not yet covered in here
        else:
            self.response_json["error"] = self.request["request_status"]
            self.response_json["log"] = "/download/faillogs/faillog-{}.txt".format(
                    self.request["request_hash"])

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR

        return self.respond()
