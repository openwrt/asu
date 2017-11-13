import os
import logging
import glob
from http import HTTPStatus

from utils.imagemeta import ImageMeta
from server.request import Request
from utils.config import Config

class ImageRequest(Request):
    def __init__(self, request_json, last_build_id):
        super().__init__(request_json)
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.last_build_id = last_build_id
        self.needed_values = ["target", "subtarget"]
        self.profile = ""

    def get_image(self, sysupgrade=False):
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
                self.response_dict["error"] = "unknown device, please check model and board params"
                return self.respond(), HTTPStatus.BAD_REQUEST

        if "network_profile" in self.request_json:
            if not self.check_network_profile():
                self.response_dict["error"] = 'network profile "{}" not found'.format(self.request_json["network_profile"])
                return self.respond(), HTTPStatus.BAD_REQUEST
        else:
            self.network_profile = ''

        self.imagemeta = ImageMeta(self.distro, self.release, self.target, self.subtarget, self.profile, self.packages, self.network_profile)
        request_id, request_hash, request_status = self.database.check_request(self.imagemeta)
        self.log.debug("found image in database: %s", request_status)
        if  request_status == "created":
            if not sysupgrade:
                file_path = self.database.get_image_path(request_id)
            else:
                file_path, file_name, checksum, filesize = self.database.get_sysupgrade(request_id)
                sysupgrade_url = "{}/static/{}{}".format(self.config.get("update_server"), file_path, file_name)
                self.response_dict["sysupgrade"] = sysupgrade_url
                # this is somewhat outdated
                self.response_dict["url"] = sysupgrade_url
                self.response_dict["checksum"] = checksum
                self.response_dict["filesize"] = filesize

            self.response_dict["files"] =  "{}/json/{}".format(self.config.get("update_server"), file_path)
            return self.respond(), HTTPStatus.OK # 200
        else:
            if request_status == "requested":
                self.response_dict["queue"] = 1 # currently not implemented
                return self.respond(), HTTPStatus.CREATED # 201
            elif request_status == "building":
                return "", HTTPStatus.PARTIAL_CONTENT # 206
            elif request_status == "build_fail":
                self.response_dict["error"] = "imagebuilder faild to create image"
                self.response_dict["log"] = "{}/static/faillogs/{}.log".format(self.config.get("update_server"), request_hash)
                return self.respond(), HTTPStatus.INTERNAL_SERVER_ERROR # 500
            elif request_status == "imagesize_fail":
                self.response_dict["error"] = "requested image is too big for requested target. retry with less packages"
                self.response_dict["log"] = "{}/static/faillogs/{}.log".format(self.config.get("update_server"), request_hash)
                return self.respond(), HTTPStatus.BAD_REQUEST # 400

        self.response_dict["error"] = request_status
        return self.respond(), 503

    def check_network_profile(self):
        network_profile = self.request_json["network_profile"]
        network_profile_path = os.path.join(self.config.get("network_profile_folder"), network_profile)
        self.log.debug("network_profile_path: %s", network_profile_path)
        self.log.debug("network_profile_folder: %s", self.config.get("network_profile_folder"))

        if os.path.isdir(network_profile_path):
            self.log.debug("found network_profile %s", network_profile)
            self.network_profile = network_profile
            return True
        self.log.debug("could not find network_profile %s", network_profile)
        return False

