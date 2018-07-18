import threading
import glob
import requests
from requests.exceptions import ConnectionError
import re
from socket import gethostname
import shutil
import json
import urllib.request
import tempfile
from datetime import datetime
import hashlib
import os
import os.path
import subprocess
import signal
import sys
import logging
import time
import os
import yaml

from worker.imagebuilder import ImageBuilder
from utils.imagemeta import ImageMeta
from utils.common import get_hash, usign_sign, usign_pubkey, usign_init
from utils.config import Config
from utils.database import Database

MAX_TARGETS=0

class Worker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")

    # write buildlog.txt to image dir
    def store_log(self, buildlog):
        self.log.debug("write log to %s", path)
        with open os.path.join(, "buildlog.txt") as buildlog_path:
            log_file = open(buildlog_path, "a")
            log_file.writelines(buildlog)

    # parse created manifest and add to database, returns hash of manifest file
    def get_manifest_hash(self, image):
        manifest_path = glob.glob(image["dir"] + "/*.manifest"))[0]
        with open(manifest_path, 'rb') as manifest_file:
            manifest_hash = hashlib.sha256(manifest_file.read()).hexdigest()[0:15]
            
        manifest_pattern = r"(.+) - (.+)\n"
        with open(manifest_path, "r") as manifest_file:
            manifest_packages = dict(re.findall(manifest_pattern, manifest_file.read()))
            self.database.add_manifest_packages(manifest_hash, manifest_packages)

        return manifest_hash

    # return dir where image is stored on server
    def get_image_dir(self, image):
        return "/".join([
            self.config.get_folder("download_folder"),
            image["distro"],
            image["release"],
            image["target"],
            image["subtarget"],
            image["profile"],
            image["manifest_hash"]
            ])

    
    # return params of array in specific order
    def image_as_array(image, extra=None):
        as_array= [
            image["distro"],
            image["release"],
            image["target"],
            image["subtarget"],
            image["profile"]
            ]
        if extra:
            as_array.append(extra)
        return as_array

    # build image
    def run_worker(self, image):
        # sort and deduplicate requested packages
        image["packages"] = sorted(list(set(image["packages"])))

        # create hash of requested packages and store in database
        image["package_hash"] = get_hash(" ".join(image["packages"]), 12)
        self.database.insert_hash(image["package_hash"], image["packages"])

        request_hash = get_hash(" ".join(image_as_array(image, image["package_hash"])), 12)

        with tempfile.TemporaryDirectory(dir=self.config.get_folder("tempdir")) as build_path:
            env = os.environ.copy()
            env.update(image)
            for key, value in image.items():
                env[key.upper()] = value

            env["j"] = str(os.cpu_count())
            env["EXTRA_IMAGE_NAME"] = request_hash
            env["BIN_DIR"] = build_path

            self.log.info("start build: %s", " ".join(cmdline))

            proc = subprocess.Popen(
                cmdline,
                cwd=build_path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT,
                env=env
            )

            output, erros = proc.communicate()
            buildlog = output.decode("utf-8")
            returnCode = proc.returncode
            if returnCode == 0:
                # calculate hash based on resulted manifest
                image["manifest_hash"] = self.get_manifest_hash(image)
                image["image_hash"] = get_hash(" ".join(image_as_array(image, image["manifest_hash"])), 15)

                # get directory where image is stored on server
                image["dir"] = self.get_image_dir(image)

                # create folder in advance
                os.makedirs(image["dir"], exist_ok=True)

                self.log.debug(os.listdir(build_path))

                # move files to new location and rename contents of sha256sums
                for filename in os.listdir(build_path):
                    new_path = os.path.join(image["dir"], self.filename_rename(filename))
                    self.log.info("move file %s", new_path)
                    shutil.move(os.path.join(build_path, filename), new_path)

                # TODO this should be done on the worker, not client
                # however, as the request_hash is changed to manifest_hash after transer
                # it not really possible... a solution would be to only trust the server
                # and add no worker keys
                #usign_sign(os.path.join(self.store_path, "sha256sums"))
                #self.log.info("signed sha256sums")

                # possible sysupgrade names, ordered by likeliness        
                possible_sysupgrade_files = [ "*-squashfs-sysupgrade.bin",
                        "*-squashfs-sysupgrade.tar", "*-squashfs.trx",
                        "*-squashfs.chk", "*-squashfs.bin",
                        "*-squashfs-sdcard.img.gz", "*-combined-squashfs*",
                        "*.img.gz"]

                sysupgrade = None

                for sysupgrade_file in possible_sysupgrade_files:
                    sysupgrade = glob.glob(os.path.join(image["dir"], sysupgrade_file))
                    if sysupgrade:
                        break

                if not sysupgrade:
                    self.log.debug("sysupgrade not found")
                    if buildlog.find("too big") != -1:
                        self.log.warning("created image was to big")
                        self.store_log(image, buildlog)
                        self.database.set_image_requests_status(request_hash, "imagesize_fail")
                        return False
                    else:
                        self.build_status = "no_sysupgrade"
                else:
                    image["sysupgrade"] = os.path.basename(sysupgrade[0])

                    self.store_log(image, buildlog)

                    self.database.add_image(image)
                    self.database.done_build_job(request_hash, image["image_hash"], build_status)
                    return True
                else:
                    self.log.info("build failed")
                    self.database.set_image_requests_status(request_hash, 'build_fail')
                    self.store_log(image, buildlog)
                    return False

                self.log.info("build successfull")

    def run(self):
        while True:
            image = self.database.get_build_job()
            if image:
                image["worker"] = "/tmp/worker"
                run_worker(image)
            time.sleep(5)

    # TODO reimplement
    #def diff_packages(self):
    #    profile_packages = self.vanilla_packages
    #    for package in self.packages:
    #        if package in profile_packages:
    #            profile_packages.remove(package)
    #    for remove_package in profile_packages:
    #        self.packages.append("-" + remove_package)

