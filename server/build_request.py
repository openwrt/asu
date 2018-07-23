import os
import logging
import glob
from http import HTTPStatus
from flask import Response

from utils.image import Image
from server.request import Request

class BuildRequest(Request):
    def __init__(self, config, db):
        super().__init__(config, db)

    def _request(self):
        self.profile = ""
        # if request_hash is available check the database directly
        if "request_hash" in self.request_json:
            self.image = self.database.check_build_request_hash(self.request_json["request_hash"])
            if not self.image
                self.response_status = HTTPStatus.NOT_FOUND
                return self.respond()
        else:
            # required params for a build request
            missing_params = check_missing_params(["distro", "release", "target", "subtarget", "profile"])
            if missing_params:
                return self.respond()

        # create image object to get the request_hash
        request_hash = get_hash(" ".join(Image(self.request_json).as_array("package_hash")), 12)
        self.image = self.database.check_build_request_hash(request_hash)

        # if found return instantly the status
        if self.image:
            self.log.debug("found image in database: %s", request_status)
            return self.return_status()

        # if not perform various checks to see if the request is acutally valid
        else:
            self.image = {}

            # check for valid distro and release/version
            bad_request = self.check_bad_request()
            if bad_request:
                return bad_request

            # check for valid target and subtarget
            bad_target = self.check_bad_target()
            if bad_target:
                return bad_target

            # check for correct packages
            bad_packages = self.check_bad_packages()
            if bad_packages:
                return bad_packages

            # calculate hash of packages
            self.params["package_hash"] = get_hash(" ".join(self.params["packages"]), 12)
            # add package_hash to database
            self.database.insert_package_hash(self.params["package_hash"], self.params["packages"])

            # now some heavy guess work is done to figure out the profile
            # eventually this could be simplified if upstream unifirm the profiles/boards
            if "board" in self.request_json:
                self.log.debug("board in request, search for %s", self.request_json["board"])
                self.profile = self.database.check_profile(self.distro, self.release, self.target, self.subtarget, self.request_json["board"])

            if not self.profile:
                if "model" in self.request_json:
                    self.log.debug("model in request, search for %s", self.request_json["model"])
                    self.profile = self.database.check_model(self.distro, self.release, self.target, self.subtarget, self.request_json["model"])
                    self.log.debug("model search found profile %s", self.profile)

            if not self.profile:
                if self.database.check_profile(self.distro, self.release, self.target, self.subtarget, "Generic"):
                    self.profile = "Generic"
                elif self.database.check_profile(self.distro, self.release, self.target, self.subtarget, "generic"):
                    self.profile = "generic"
                else:
                    self.response_json["error"] = "unknown device, please check model and board params"
                    self.response_status = HTTPStatus.PRECONDITION_FAILED # 412
                    return self.respond()

            # all checks passed, eventually add to queue!
            self.database.add_build_job(self.image)
            return self.return_queued()

    def return_queued(self):
        self.response_header["X-Imagebuilder-Status"] = "queue"
        self.response_header['X-Build-Queue-Position'] = '1337' # TODO: currently not implemented
        self.response_json["request_hash"] = request_hash

        self.response_status = HTTPStatus.ACCEPTED # 202
        return self.respond()

    def return_status(self):
        # image created, return all desired information
        if self.image["status"] == "created":
            file_path, sysupgrade = self.database.get_sysupgrade(self.image["image_hash"])
            self.response_json["sysupgrade"] = "{}/static/{}{}".format(self.config.get("server"), file_path, sysupgrade)
            self.response_json["log"] = "{}/static/{}/buildlog.txt".format(self.config.get("server"), file_path)
            self.response_json["files"] =  "{}/json/{}".format(self.config.get("server"), file_path)
            self.response_json["request_hash"] = self.image["request_hash"]
            self.response_json["image_hash"] = self.image["image_hash"]

            self.response_status = HTTPStatus.OK # 200

        # no sysupgrade found but requested, let user figure out what to do
        elif self.image["status"] == "no_sysupgrade" and self.sysupgrade:
            self.response_json["error"] = "No sysupgrade file produced, may not supported by modell."

            self.response_status = HTTPStatus.NOT_IMPLEMENTED # 501

        # no sysupgrade found but not requested, factory image is likely from interest
        elif self.image["status"] == "no_sysupgrade" and not self.sysupgrade:
            file_path = self.database.get_image_path(image_hash)
            self.response_json["files"] =  "{}/json/{}".format(self.config.get("server"), file_path)
            self.response_json["log"] = "{}/static/{}build-{}.log".format(self.config.get("server"), file_path, image_hash)
            self.response_json["request_hash"] = request_hash
            self.response_json["image_hash"] = image_hash

            self.response_status = HTTPStatus.OK # 200

        # image request passed validation and is queued
        elif self.image["status"] == "requested":
            self.return_queued()

        # image is currently building
        elif self.image["status"] == "building":
            self.response_header["X-Imagebuilder-Status"] = "building"
            self.response_json["request_hash"] = self.image["request_hash"]

            self.response_status = HTTPStatus.ACCEPTED # 202

        # build failed, see build log for details
        elif self.image["status"] == "build_fail":
            self.response_json["error"] = "imagebuilder faild to create image"
            self.response_json["log"] = "{}/static/faillogs/faillog-{}.txt".format(self.config.get("server"), self.image["request_hash"])
            self.response_json["request_hash"] = self.image["request_hash"]

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR # 500

        # likely to many package where requested
        elif self.image["status"] == "imagesize_fail":
            self.response_json["error"] = "No firmware created due to image size. Try again with less packages selected."
            self.response_json["log"] = "{}/static/faillogs/request-{}.log".format(self.config.get("server"), request_hash)
            self.response_json["request_hash"] = request_hash

            self.response_status = 413 # PAYLOAD_TO_LARGE RCF 7231

        # something happend with is not yet covered in here
        else:
            self.response_json["error"] = self.image["status"]

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR

        return self.respond()
