from flask import Flask
import time
import threading
from queue import Queue
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

database = Database()

app = Flask(__name__)

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
    self.log.warning("download image")
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
        ir = ImageRequest(request_json, build_manager.get_last_build_id())
        return ir.get_sysupgrade()

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

class BuildManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()

    def run(self):
        self.last_build_id = 0
        while True:
            build_job_request = self.database.get_build_job()
            if build_job_request:
                self.last_build_id = build_job_request[0]
            if not build_job_request:
                self.log.debug("build queue is empty")
                time.sleep(5)
            else:
                image = Image(*build_job_request[2:8])
                if not image.created():
                    if image.run():
                        self.database.del_build_job(build_job_request[1])
                    else:
                        self.database.set_build_job_fail(build_job_request[1])
                        self.log.warn("build failed for %s", image.name)

    def get_last_build_id(self):
        return self.last_build_id

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    build_manager = BuildManager()
    build_manager.start()

    app.run()
