from image import Image
from request import Request

class ImageRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.needed_values = ["distro", "target", "subtarget", "board", "packages"]

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.profile = self.request_json["board"]
        if not self.check_profile:
            self.response_dict["error"] = "board not found"
            return self.respond(), 400
        
        image = Image()
        image.request_variables(self.distro, self.version, self.target, self.subtarget, self.profile, self.packages)

        self.response_dict["url"] =  self.update_server_url + "/" + image.get()
        return self.respond(), 200

    def check_profile(self):
        if database.check_target(self.target, self.subtarget, self.profile):
            return True
        return False
