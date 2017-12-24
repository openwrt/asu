from flask import Flask
from flask import render_template
import logging
from os import makedirs
from shutil import copyfile

from utils.config import Config
from utils.common import init_usign

app = Flask(__name__)

import server.views

config = Config()

makedirs("{}/{}".format(config.get_folder("downloaddir"), "faillogs"), exist_ok=True)
if config.get("sign_images"):
    print("sign workers")
    init_usign()
    copyfile(config.get_folder("key_folder") + "/public", config.get_folder("worker_keys") + "/server")

