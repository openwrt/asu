from image import Image
from config import Config
from request import Request

class ImageRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.config = Config()
        self.needed_values = ["distro", "version", "target", "subtarget", "board", "packages"]

    def get_sysupgrade(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.profile = self.request_json["board"]
        if not self.check_profile:
            self.response_dict["error"] = "board not found"
            return self.respond(), 400

        
        if "network_profile" in self.request_json:
            if self.check_network_profile():
                self.request_json["error"] = "network profile not found"
                return self.respond(), 400
        else:
            self.network_profile = None
        
        self.image = Image(self.distro, self.version, self.target, self.subtarget, self.profile, self.packages, self.network_profile)

        if self.image.created():
            self.response_dict["url"] =  self.config.get("update_server") + "/" + self.image.get_sysupgrade()
            return self.respond(), 200
        else:
            print(self.database.add_build_job(self.image))
            return "", 206
                #self.response_dict["queue"] = self.build_queue.qsize()
       #         return "", 201
       #     else:
       #         return "", 206

    def check_profile(self):
        if database.check_target(self.target, self.subtarget, self.profile):
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
