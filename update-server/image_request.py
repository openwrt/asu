from image import Image
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
        self.needed_values = ["distro", "version", "target", "subtarget", "board", "packages"]

    def get_sysupgrade(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.profile = self.request_json["board"]
        if not self.check_profile:
            self.response_dict["error"] = "board not found"
            return self.respond(), HTTPStatus.BAD_REQUEST

        if "packages" in self.request_json:
            self.packages = self.request_json["packages"]
            all_found, missing_package = self.check_packages()
            if not all_found:

                self.response_dict["error"] = "could not find package {} for requested target".format(missing_package)
                return self.respond(), HTTPStatus.BAD_REQUEST
        
        if "network_profile" in self.request_json:
            if self.check_network_profile():
                self.request_json["error"] = "network profile not found"
                return self.respond(), HTTPStatus.BAD_REQUEST
        else:
            self.network_profile = None
        
        self.image = Image(self.distro, self.release, self.target, self.subtarget, self.profile, self.packages, self.network_profile)

        if self.image.created():
            self.response_dict["url"] =  self.config.get("update_server") + "/" + self.image.get_sysupgrade()
            return self.respond(), HTTPStatus.OK
        else:
            response = self.database.add_build_job(self.image)
            if response[1] == 1:
                queue_position = response[0] - self.last_build_id
                if queue_position < 0:
                    queue_position = 0
                self.response_dict["queue"] = queue_position
                return self.respond(), HTTPStatus.CREATED 

            elif response[1] == 0:
                return "", HTTPStatus.PARTIAL_CONTENT
            elif response[1] == 2:
                self.response_dict["error"] = "imagebuilder faild to create image - techniker ist informiert"
                return self.respond(), HTTPStatus.INTERNAL_SERVER_ERROR

    def check_profile(self):
        if database.check_target(self.distro, self.release, self.target, self.subtarget, self.profile):
            return True
        return False

    def check_network_profile(self):
        network_profile = self.request_json["network_profile"]
        network_profile_path = os.path.join(selt.config.get("network_profile_folder"), network_profile)

        if os.path.isdir(network_profile_path):
            self.log.debug("found network_profile %s", network_profile)
            self.network_profile = network_profile
            return True
        self.log.debug("could not find network_profile %s", network_profile)
        return False

    def check_packages(self):
        available_packages = self.database.get_available_packages(self.distro, self.release, self.target, self.subtarget).keys()
        for package in self.packages:
            if package not in available_packages:
                logging.warning("could not find package {}".format(package))
                return False, package
        return True, None
