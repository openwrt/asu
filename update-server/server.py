from flask import Flask
from build_manager import BuildManager
import socket
import time
import threading
from queue import Queue
import json
import sys
from image import ImageBuilder
from database import Database
import logging
from util import get_dir
from flask import request, send_from_directory,redirect
import os
from image import Image
from replacement_table import *
from update_request import UpdateRequest
from image_request import ImageRequest
from config import Config
from http import HTTPStatus

database = Database()
config = Config()

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
    # offer file to download
    # redirect to image so nginx handels download
    # raise image download counter
    
    database.increase_downloads(os.path.join(image_path, image_name))

    # use different approach?
    if not config.get("dev"):
        return redirect(os.path.join(config.get("update_server"), "static", image_path, image_name), HTTPStatus.FOUND)
    return send_from_directory(directory=os.path.join(get_dir("downloaddir"), image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/image-request", methods=['GET', 'POST'])
def requst_image():
    if request.method == 'POST':
        request_json = request.get_json()
        ir = ImageRequest(request_json, get_last_build_id())
        return ir.get_sysupgrade()

# may show some stats
@app.route("/")
def rootPath():
    response = "update server running<br>"
    response += "currently supported<br>"
    for target, subtarget, supported in database.get_targets("lede", "17.01.2"):
        if supported:
            response += "{} - {}<br>".format(target, subtarget)
    return response

def get_last_build_id():
    if config.get("dev"):
        return bm.get_last_build_id()

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    socket_name = "/tmp/build_manager_last_build_id"
    try:
        client.connect(socket_name)
    except socket.error as msg:
        print("build manager not running")
        quit(1)
    try:
        return int(client.recv(16).decode())
    finally:
        client.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if config.get("dev"):
        bm = BuildManager()
        bm.start()
    #get_last_build_id()

    if config.get("dev"):
        app.run(host="0.0.0.0")
    else:
        app.run()
