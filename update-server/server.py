from flask import Flask
import sys
from flask import request, send_from_directory
import os
from image import Image
from replacement_table import *

app = Flask(__name__)
distro_releases = {}
distro_releases["lede"] = "17.01.1"

# returns the current release
# TODO: this won't be static later
@app.route("/current-release/<distro>")
def currentRelease(distro):
    distro = distro.lower()
    if distro in distro_releases:
        return distro_releases[distro]
    return "unknown release", 404

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def downloadImage(image_path, image_name):
    # offer file to download
    # security issue using ../../whatever.py?
    return send_from_directory(directory=os.path.join("download", image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/request-image", methods=['GET', 'POST', 'PUT'])
def requstImage():
    if request.method == 'POST':
        jsonOutput = request.get_json()
        if not check_image_request(request.get_json()):
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
def check_image_request(request):
    # right now this approach is dead simple
    values = ["distro", "version", "target", "subtarget"]
    for value in values:
        if not value in request:
            return False
    return True


if __name__ == "__main__":
    app.run()
