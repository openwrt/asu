from image import Image
import os
import logging
from config import Config
from request import Request
from http import HTTPStatus

class ImageRequest(Request):
    def __init__(self, request_json, last_build_id):
        super().__init__(request_json)
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.last_build_id = last_build_id
        self.needed_values = ["distro", "version", "target", "subtarget", "board"]

    def get_sysupgrade(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        profile_request = self.database.check_profile(self.distro, self.release, self.target, self.subtarget, self.request_json["board"])
        if profile_request:
            self.profile = profile_request
        else:
            if self.database.check_profile(self.distro, self.release, self.target, self.subtarget, "Generic"):
                self.profile = "Generic"
            else:
                # added due to different values of board_name (e.g. ubnt-loco-m-xw (ImageBuilder) vs. loco-m-w (device))
                # see https://github.com/aparcar/gsoc17-attended-sysupgrade/issues/26
                if "model" in self.request_json:
                    profile_request = self.database.check_model(self.distro, self.release, self.target, self.subtarget, self.request_json["model"])
                else:
                    self.request_json["model"] = "unknown"

                if profile_request:
                    self.profile = profile_request
                else:
                    self.response_dict["error"] = "unknown board: {}/{}".format(self.request_json["board"], self.request_json["model"] )
                    return self.respond(), HTTPStatus.BAD_REQUEST

        self.packages = None
        if "packages" in self.request_json:
            self.packages = self.request_json["packages"]
            all_found, missing_package = self.check_packages()
            if not all_found:
                self.response_dict["error"] = "could not find package {} for requested target".format(missing_package)
                return self.respond(), HTTPStatus.BAD_REQUEST

        if "network_profile" in self.request_json:
            if not self.check_network_profile():
                self.response_dict["error"] = 'network profile "{}" not found'.format(self.request_json["network_profile"])
                return self.respond(), HTTPStatus.BAD_REQUEST
        else:
            self.network_profile = ''

        self.image = Image(self.distro, self.release, self.target, self.subtarget, self.profile, self.packages, self.network_profile)
        response = self.database.check_request(self.image)
        request_id, request_hash, request_status = response
        self.log.debug("found image in database: %s", request_status)
        if  request_status == "created":
            filename, checksum, filesize = self.database.get_image(request_id)
            self.response_dict["url"] =  "{}/download/{}".format(self.config.get("update_server"), filename)
            self.response_dict["checksum"] = checksum
            self.response_dict["filesize"] = filesize
            return self.respond(), HTTPStatus.OK # 200
        else:
            if request_status == "requested":
                self.response_dict["queue"] = 1 # currently not implemented
                return self.respond(), HTTPStatus.CREATED # 201
            elif request_status == "building":
                return "", HTTPStatus.PARTIAL_CONTENT # 206
            elif request_status == "failed":
                self.response_dict["error"] = "imagebuilder faild to create image - techniker ist informiert"
                self.response_dict["log"] = "{}/static/faillogs/{}.log".format(self.config.get("update_server"), request_hash)
                return self.respond(), HTTPStatus.INTERNAL_SERVER_ERROR # 500
            elif request_status == "imagesize_fail":
                self.response_dict["error"] = "requested image is too big for requested target. retry with less packages"
                self.response_dict["log"] = "{}/static/faillogs/{}.log".format(self.config.get("update_server"), request_hash)
                return self.respond(), HTTPStatus.BAD_REQUEST # 400
        return 503

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

    def check_packages(self):
        available_packages = self.database.get_packages_available(self.distro, self.release, self.target, self.subtarget).keys()
        for package in self.packages:
            if package == "kernel":
                pass # kernel is not an installable package, but installed...
            elif package not in available_packages:
                logging.warning("could not find package {}".format(package))
                return False, package
        return True, None
