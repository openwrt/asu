from flask import Flask
from flask import render_template
import logging

from utils.config import Config
from utils.common import create_folder, get_folder, init_usign

app = Flask(__name__)

import server.views

config = Config().load()
create_folder("{}/{}".format(get_folder("downloaddir"), "faillogs"))
if config.get("sign_images"):
    print("sign images")
    init_usign()

if config.get("dev"):
    from worker.worker import Worker
    worker = Worker()
    worker.start()
    #app.debug = True

