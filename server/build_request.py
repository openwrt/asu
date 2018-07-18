import os
import logging
import glob
from http import HTTPStatus
from flask import Response

from utils.imagemeta import ImageMeta
from server.request import Request

class BuildRequest(Request):
    def __init__(self, config, db):
        super().__init__(config, db)

    def _request(self):
        self.profile = ""
        if not "request_hash" in self.request_json and not ("target" in self.request_json and "subtarget" in self.request_json):
            self.response_status = HTTPStatus.BAD_REQUEST
            return self.respond()

        if "request_hash" in self.request_json:
            check_result = self.database.check_build_request_hash(self.request_json["request_hash"])
            if check_result:
                image_hash, request_id, request_hash, request_status = check_result
            else:
                self.response_status = HTTPStatus.NOT_FOUND
                return self.respond()
        else:
            bad_request = self.check_bad_request()
            if bad_request:
                return bad_request

            bad_target = self.check_bad_target()
            if bad_target:
                return bad_target

            bad_packages = self.check_bad_packages()
            if bad_packages:
                return bad_packages

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

            self.imagemeta = ImageMeta(self.distro, self.release, self.target, self.subtarget, self.profile, self.packages)
            image_hash, request_id, request_hash, request_status = self.database.check_build_request(self.imagemeta)
            self.log.debug("found image in database: %s", request_status)

        # the sysupgrade should be stored in a different way but works for now
        if request_status == "created":
            file_path, sysupgrade = self.database.get_sysupgrade(image_hash)
            self.response_json["sysupgrade"] = "{}/static/{}{}".format(self.config.get("server"), file_path, sysupgrade)
            self.response_json["log"] = "{}/static/{}build-{}.log".format(self.config.get("server"), file_path, image_hash)
            self.response_json["files"] =  "{}/json/{}".format(self.config.get("server"), file_path)
            self.response_json["request_hash"] = request_hash
            self.response_json["image_hash"] = image_hash

            self.response_status = HTTPStatus.OK # 200

        elif request_status == "no_sysupgrade" and self.sysupgrade:
            self.response_json["error"] = "No sysupgrade file produced, may not supported by modell."

            self.response_status = HTTPStatus.NOT_IMPLEMENTED # 501

        elif request_status == "no_sysupgrade" and not self.sysupgrade:
            file_path = self.database.get_image_path(image_hash)
            self.response_json["files"] =  "{}/json/{}".format(self.config.get("server"), file_path)
            self.response_json["log"] = "{}/static/{}build-{}.log".format(self.config.get("server"), file_path, image_hash)
            self.response_json["request_hash"] = request_hash
            self.response_json["image_hash"] = image_hash

            self.response_status = HTTPStatus.OK # 200

        elif request_status == "requested":
            self.response_json["queue"] = 1337 # TODO: currently not implemented
            self.response_header["X-Imagebuilder-Status"] = "queue"
            self.response_header['X-Build-Queue-Position'] = '1337' # TODO: currently not implemented
            self.response_json["request_hash"] = request_hash

            self.response_status = HTTPStatus.ACCEPTED # 202

        elif request_status == "building":
            self.response_header["X-Imagebuilder-Status"] = "building"

            self.response_json["request_hash"] = request_hash

            self.response_status = HTTPStatus.ACCEPTED # 202

        elif request_status == "build_fail":
            self.response_json["error"] = "imagebuilder faild to create image"
            self.response_json["log"] = "{}/static/faillogs/request-{}.log".format(self.config.get("server"), request_hash)
            self.response_json["request_hash"] = request_hash

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR # 500

        elif request_status == "imagesize_fail":
            self.response_json["error"] = "No firmware created due to image size. Try again with less packages selected."
            self.response_json["log"] = "{}/static/faillogs/request-{}.log".format(self.config.get("server"), request_hash)
            self.response_json["request_hash"] = request_hash

            self.response_status = 413 # PAYLOAD_TO_LARGE RCF 7231
        else:
            self.response_json["error"] = request_status

            self.response_status = HTTPStatus.INTERNAL_SERVER_ERROR

        return self.respond()
