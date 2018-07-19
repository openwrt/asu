import threading
import glob
import requests
from requests.exceptions import ConnectionError
import re
from socket import gethostname
import shutil
import json
import urllib.request
import zipfile
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

from utils.image import Image
from utils.common import get_hash
from utils.config import Config
from utils.database import Database

class Worker(threading.Thread):
    def __init__(self, job, worker, params):
        self.job = job
        self.worker = worker
        self.params = params
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")

    def setup_meta(self):
        self.log.debug("setup meta")
        os.makedirs(self.worker, exist_ok=True)
        url = "https://github.com/aparcar/meta-imagebuilder/archive/master.zip"
        urllib.request.urlretrieve(url, "meta.zip")
        zip_ref = zipfile.ZipFile("meta.zip", 'r')
        zip_ref.extractall(self.worker)
        zip_ref.close()

    def setup(self):
        self.log.debug("setup")

        return_code, output, errors = self.run_meta("download_ib")
        if return_code == 0:
            self.log.info("setup complete")
        else:
            self.log.error("failed to download imagebuilder")
            print(output)
            print(errors)
            exit()

    # build image
    def build(self):
        self.image = Image(self.params["image"])

        request_hash = get_hash(" ".join(self.image.as_array("package_hash"), 12))

        with tempfile.TemporaryDirectory(dir=self.config.get_folder("tempdir")) as build_path:

            self.params["j"] = str(os.cpu_count())
            self.params["EXTRA_IMAGE_NAME"] = request_hash
            self.params["BIN_DIR"] = build_path

            self.log.info("start build: %s", " ".join(cmdline))

            return_code, output, errors = self.run_meta("image")

            if return_code == 0:
                # move manifest first to calculate image hash
                manifest_path = glob.glob(build_dir + "/*.manifest")[0]
                if manifest_path:
                    shutil.move(manifest_path, self.image.get("dir"))
                else:
                    self.log.error("Could not find manifest file")
                    return 0

                # calculate hash based on resulted manifest
                self.image.manifest_hash()
                self.image.image_hash()

                # get directory where image is stored on server
                image_dir = self.image.set_image_dir()

                # create folder in advance
                os.makedirs(self.image.get("dir"), exist_ok=True)

                self.log.debug(os.listdir(build_path))

                # move files to new location and rename contents of sha256sums
                # TODO rename request_hash to manifest_hash
                for filename in os.listdir(build_path):
                    shutil.move(build_path + "/" + filename, image_dir)

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
                    sysupgrade = glob.glob(image_dir, sysupgrade_file)
                    if sysupgrade:
                        break

                if not sysupgrade:
                    self.log.debug("sysupgrade not found")
                    if buildlog.find("too big") != -1:
                        self.log.warning("created image was to big")
                        self.image.store_log(buildlog)
                        self.database.set_image_requests_status(request_hash, "imagesize_fail")
                        return False
                    else:
                        self.build_status = "no_sysupgrade"
                else:
                    self.image.set("sysupgrade", os.path.basename(sysupgrade[0]))

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
        if not os.path.exists(self.worker + "/meta"):
            self.setup_meta()
        self.setup()
        if self.job == "build":
            self.build()
        elif self.job == "info":
            self.parse_info()
        elif self.job == "packages":
            self.parse_packages()

    def run_meta(self, cmd):
        print(self.params)
        env = os.environ.copy()
        for key, value in self.params.items():
            print(key, value)
            env[key.upper()] = value

        proc = subprocess.Popen(
            ["sh", "meta", cmd],
            cwd=self.worker,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT,
            env=env
        )

        output, errors = proc.communicate()
        return_code = proc.returncode
        output = output.decode('utf-8')

        return (return_code, output, errors)


    def parse_info(self):
        self.log.debug("parse info")

        return_code, output, errors = self.run_meta("info")

        if return_code == 0:
            default_packages_pattern = r"(.*\n)*Default Packages: (.+)\n"
            default_packages = re.match(default_packages_pattern, output, re.M).group(2)
            logging.debug("default packages: %s", default_packages)

            profiles_pattern = r"(.+):\n    (.+)\n    Packages: (.*)\n"
            profiles = re.findall(profiles_pattern, output)
            print(profiles)
            if not profiles:
                profiles = []
            print(self.params)
            self.database.insert_profiles(self.params, default_packages, profiles)
        else:
            logging.error("could not receive profiles")
            return False

    def parse_packages(self):
        self.log.info("receive packages")

        return_code, output, errors = self.run_meta("package_list")

        if return_code == 0:
            packages = re.findall(r"(.+?) - (.+?) - .*\n", output)
            self.log.info("found {} packages for {} {} {} {}".format(len(packages)))
            self.database.insert_packages_available(self.params, packages)
        else:
            self.log.warning("could not receive packages")

if __name__ == '__main__':
    config = Config()
    database = Database(config)
    while True:
        worker = "/tmp/worker"
        image = database.get_build_job()
        if image != None:
            job = "build"
            worker = Worker(job, worker, image)
            worker.run() # TODO no threading just yet
        outdated_subtarget = database.get_subtarget_outdated()
        if outdated_subtarget:
            print(outdated_subtarget.cursor_description)
            job = "info"
            worker = Worker(job, worker, image)
            worker.run()
            job = "packages"
            worker = Worker(job, worker, image)
            worker.run()
        time.sleep(5)

    # TODO reimplement
    #def diff_packages(self):
    #    profile_packages = self.vanilla_packages
    #    for package in self.packages:
    #        if package in profile_packages:
    #            profile_packages.remove(package)
    #    for remove_package in profile_packages:
    #        self.packages.append("-" + remove_package)

