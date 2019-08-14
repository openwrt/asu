from http import HTTPStatus
import json
from sys import getsizeof
import os

from asu.utils.common import get_hash, get_packages_hash, get_request_hash
from asu.request import Request


class BuildRequest(Request):
    """Handle build requests"""

    def __init__(self, config, db):
        super().__init__(config, db)

    def _process_request(self):
        self.log.debug("request: %s", self.request)

        # if request_hash is available check the database directly
        if "request_hash" in self.request:
            self.request = self.database.check_request_hash(
                self.request["request_hash"]
            )

            if not self.request:
                self.response_status = HTTPStatus.NOT_FOUND
                return self.respond()
            else:
                return self.return_status()

        request_hash = get_request_hash(self.request)
        request_database = self.database.check_request_hash(request_hash)

        # if found return instantly the status
        if request_database:
            self.log.debug(
                "found image in database: %s", request_database["request_status"]
            )
            self.request = request_database
            return self.return_status()
        else:
            self.request["request_hash"] = request_hash
            self.response_json["request_hash"] = self.request["request_hash"]

        # validate attached defaults
        if "defaults" in self.request:
            if self.request["defaults"]:
                # check if the uci file exceeds the max file size. this should
                # be done as the uci-defaults are at least temporary stored in
                # the database to be passed to a worker
                if getsizeof(self.request["defaults"]) > self.config.get(
                    "max_defaults_size", 1024
                ):
                    self.response_json["error"] = "attached defaults exceed max size"
                    self.response_status = (
                        420
                    )  # this error code is the best I could find
                    return self.respond()
                else:
                    self.request["defaults_hash"] = get_hash(
                        self.request["defaults"], 32
                    )
                    self.database.insert_defaults(
                        self.request["defaults_hash"], self.request["defaults"]
                    )

        # add package_hash to database
        if "packages" in self.request:
            # check for existing packages
            bad_packages = self.check_bad_packages(self.request["packages"])
            if bad_packages:
                return bad_packages
            self.request["packages_hash"] = get_packages_hash(self.request["packages"])
            self.database.insert_packages_hash(
                self.request["packages_hash"], self.request["packages"]
            )

        # all checks passed, add job to queue!
        self.log.debug("add build job %s", self.request)
        self.database.add_build_job(self.request)
        return self.return_queued()

    def return_queued(self):
        self.response_header["X-Imagebuilder-Status"] = "queue"
        if "build_position" in self.request:
            self.response_header["X-Build-Queue-Position"] = self.request[
                "build_position"
            ]
        self.response_json["request_hash"] = self.request["request_hash"]

        self.response_status = HTTPStatus.ACCEPTED  # 202
        return self.respond()

    def return_status(self):
        # image created, return all desired information
        if self.request["request_status"] == "created":
            self.database.cache_hit(self.request["image_hash"])
            image = self.database.get_image(self.request["image_hash"])

            self.response_json["request_hash"] = self.request["request_hash"]
            self.response_json["image_hash"] = self.request["image_hash"]
            self.response_json["manifest_hash"] = image["manifest_hash"]
            self.response_json["image_folder"] = "/download/" + image["image_folder"]
            self.response_json["image_prefix"] = image["image_prefix"]
            with open(
                os.path.join(
                    self.config.get_folder("download_folder"),
                    image["image_folder"],
                    image["image_prefix"],
                )
                + ".json"
            ) as json_info:
                self.response_json.update(json.load(json_info))
            self.response_status = HTTPStatus.OK  # 200

            return self.respond()

        # image request passed validation and is queued
        elif self.request["request_status"] == "requested":
            self.return_queued()

        # image is currently building
        elif self.request["request_status"] == "building":
            self.response_header["X-Imagebuilder-Status"] = "building"
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = HTTPStatus.ACCEPTED  # 202

        # build failed, see build log for details
        elif self.request["request_status"] == "build_fail":
            self.response_json["error"] = "ImageBuilder faild to create image"
            self.response_json["faillog"] = "/download/faillogs/faillog-{}.txt".format(
                self.request["request_hash"]
            )
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR  # 500

        # creation of manifest failed, package conflict
        elif self.request["request_status"] == "manifest_fail":
            self.response_json[
                "error"
            ] = "Incompatible package selection. See build log for details"
            self.response_json["log"] = "/download/faillogs/faillog-{}.txt".format(
                self.request["request_hash"]
            )
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = HTTPStatus.CONFLICT  # 409

        # likely to many package where requested
        elif self.request["request_status"] == "imagesize_fail":
            self.response_json[
                "error"
            ] = "Image size exceeds device storage. Retry with less packages"
            self.response_json["log"] = "/download/faillogs/faillog-{}.txt".format(
                self.request["request_hash"]
            )
            self.response_json["request_hash"] = self.request["request_hash"]

            self.response_status = 413  # PAYLOAD_TO_LARGE RCF 7231

        # something happend with is not yet covered in here
        else:
            self.response_json["error"] = self.request["request_status"]
            self.response_json["log"] = "/download/faillogs/faillog-{}.txt".format(
                self.request["request_hash"]
            )

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR

        return self.respond()
