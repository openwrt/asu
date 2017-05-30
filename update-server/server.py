from flask import Flask
import json
from distutils.version import LooseVersion
import sys
from image import ImageBuilder
from database import Database
import logging
from flask import request, send_from_directory
import os
from image import Image
from replacement_table import *

logging.basicConfig(level=logging.DEBUG)
database = Database()

app = Flask(__name__)
distro_releases = {}
distro_releases["lede"] = ["17.01.1", "17.01.0"]

# returns the current release
# TODO: this won't be static later
@app.route("/current-release/<distro>")
def currentRelease(distro):
    distro = distro.lower()
    if distro in distro_releases:
        return distro_releases[distro]
    return "unknown release", 404

@app.route("/update-request", methods=['POST'])
def update_request():
    if request.method == 'POST':
        request_json = request.get_json()
        ur = UpdateRequest(request_json)
        return ur.run()
    return 444

class UpdateRequest():
    def __init__(self, request_json, check_packages=True):
        self.request_json = request_json
        self.response_dict = {}

    def run(self):

        if not self.vaild_request():
            self.response_dict["message"] = "missing parameters\nneed %s" % " ".join(self.needed_values)
            return self.respond()

        self.distro = self.request_json["distro"].lower()

        if not self.distro in distro_releases:
            self.response_dict["message"] = "unknown distribution %s" % self.distro
            return self.respond()

        self.latest_version = distro_releases[self.distro][0]

        self.version = self.request_json["version"]
        if not self.version in distro_releases[self.distro]:
            self.response_dict["message"] = "unknown release %s" % self.version
            return self.respond()

        self.target = self.request_json["target"]
        self.subtarget = self.request_json["subtarget"]

        if not self.check_target():
            self.response_dict["message"] = "unknown target %s/%s" % (self.target, self.subtarget)
            return self.respond()

        if not self.version_latest():
            self.response_dict["version"] = self.latest_version

        if "packages" in self.request_json and check_packages:
            self.packages = self.request_json["packages"]
            self.check_packages()

        return self.respond()

    def vaild_request(self):
        # needed params to check sysupgrade
        self.needed_values = ["distro", "version", "target", "subtarget"]
        for value in self.needed_values:
            if not value in self.request_json:
                return False
        return True

    # not sending distro/version. does this change within releases?
    def check_target(self):
        if database.check_target(self.target, self.subtarget):
            return True
        return False

    def check_packages(self):
        latest_packages = database.check_packages(self.target, self.subtarget, self.packages.keys())

    def init_imagebuilder(self):
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)

    def respond(self):
        return(json.dumps(self.response_dict))
   
    # if local version is newer than received returns true
    def version_latest(self):
        return LooseVersion(self.version) >= LooseVersion(self.latest_version)

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def download_image(image_path, image_name):
    # offer file to download
    # security issue using ../../whatever.py?
    return send_from_directory(directory=os.path.join("download", image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/image-request", methods=['GET', 'POST', 'PUT'])
def requst_image():
    if request.method == 'POST':
        jsonOutput = request.get_json()
        if not check_request(request.get_json()):
            return "", 400

        image = Image()
        jsonOutput["profile"] = translate_machine(jsonOutput["machine"])
        image.request_params(jsonOutput)
        return image.get()

        
    else:
        return("get")
        return(request.args.get('release'))
    pass

def translate_machine(machine):
    machines = {}
    machines["TP-LINK CPE510/520"] = "cpe510-520"

   # if not machine in machines:
   #     return None
    return machines[machine]

# foobar
@app.route("/")
def rootPath():
    return "update server running"

def updatePackages(version, packages):
    pass

# check if the received image request is vaild
def check_request(request):
    # right now this approach is dead simple
    values = ["distro", "version", "target", "subtarget"]
    for value in values:
        if not value in request:
            return False
    return True


if __name__ == "__main__":
    app.run()
