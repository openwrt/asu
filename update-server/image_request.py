from image import Image
from config import Config
from request import Request

class ImageRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.config = Config()
        self.needed_values = ["distro", "target", "subtarget", "board", "packages"]

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.profile = self.request_json["board"]
        if not self.check_profile:
            self.response_dict["error"] = "board not found"
            return self.respond(), 400

        if "network_profile" in self.request_json and not self.check_network_profile():
            self.request_json["error"] = "network profile not found"
            return self.respond(), 400
        
        image = Image()
        image.request_variables(self.distro, self.version, self.target, self.subtarget, self.profile, self.packages, self.network_profile)

        self.response_dict["url"] =  self.config.get("update_server") + "/" + image.get_sysupgrade()
        return self.respond(), 200

    def check_profile(self):
        if database.check_target(self.target, self.subtarget, self.profile):
            return True
        return False

    def check_network_profile(self):
        network_profile_path = os.path.join(selt.config.get("network_profile_folder"), network_profile)
        if os.path.isdir(network_profile_path):
            logging.debug("found network_profile %s", network_profile)
            return True
        logging.debug("could not find network_profile %s", network_profile)
        return False
