from flask import Flask
import json
import sys
from image import ImageBuilder
from database import Database
import logging
from flask import request, send_from_directory
import os
from image import Image
from replacement_table import *
from update_request import UpdateRequest
from image_request import ImageRequest

logging.basicConfig(level=logging.DEBUG)
database = Database()

app = Flask(__name__)
distro_releases = {}
distro_releases["lede"] = ["17.01.1", "17.01.0"]

@app.route("/update-request", methods=['POST'])
def update_request():
    if request.method == 'POST':
        request_json = request.get_json()
        ur = UpdateRequest(request_json)
        return ur.run()
    return 400

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def download_image(image_path, image_name):
    logging.warning("download image")
    # offer file to download
    # security issue using ../../whatever.py?
    # redirect to image so nginx handels download
    # raise image download counter
    return send_from_directory(directory=os.path.join("download", image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/image-request", methods=['GET', 'POST', 'PUT'])
def requst_image():
    if request.method == 'POST':
        request_json = request.get_json()
        ir = ImageRequest(request_json)
        return ir.run()

# may show some stats
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
    app.run(host='0.0.0.0')
