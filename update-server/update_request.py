from request import Request
from http import HTTPStatus

class UpdateRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.needed_values = ["distro", "version", "target", "subtarget"]

    def run(self):
        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        self.latest_version = self.distro_versions[self.distro][0]

        if not self.version_latest(self.latest_version, self.version):
            self.response_dict["version"] = self.latest_version
            print("ack")
            return self.respond(), HTTPStatus.OK


        return("", HTTPStatus.NO_CONTENT)
