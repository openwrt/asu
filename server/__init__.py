from flask import Flask
from flask import render_template
import logging
from os import makedirs
from shutil import copyfile

from utils.config import Config
from utils.common import usign_init, gpg_gen_key, gpg_init

app = Flask(__name__)

import server.views

config = Config()

makedirs(config.get_folder("download_folder") + "/faillogs", exist_ok=True)

# folder to include server keys in created images
makedirs(config.get_folder("keys_public") + "/server/etc/", exist_ok=True)

if config.get("sign_images"):
    print("sign workers")
    usign_init()
    gpg_init()
    gpg_gen_key("test@test.de")
    copyfile(config.get_folder("keys_private") + "/public", config.get_folder("keys_public") + "/server/etc/server.pub")
    copyfile(config.get_folder("keys_private") + "/public.gpg", config.get_folder("keys_public") + "/server/etc/server.gpg")

