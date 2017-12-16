import threading
from zipfile import ZipFile
import glob
import re
from socket import gethostname
import shutil
import json
import urllib.request
import tempfile
from datetime import datetime
import requests
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
from utils.common import create_folder, get_hash, get_folder, setup_gnupg, sign_file, get_pubkey
from utils.config import Config

MAX_TARGETS=0

class Worker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config("worker.yml")
        self.log.info("config initialized")
        self.worker_id = None
        self.imagebuilders = set()
        self.auth = (self.config.get("worker"), self.config.get("password"))

    def worker_register(self):
        params = {}
        params["worker_name"] = gethostname()
        params["worker_address"] = ""
        params["worker_pubkey"] = get_pubkey()
        self.log.info("register worker '%s' '%s' '%s'", *params)

        self.worker_id = requests.post(self.config.get("server") + "/worker/register", json=params, auth=self.auth).json()

    def worker_add_skill(self, imagebuilder):
        params = {}
        params["worker_id"] = self.worker_id
        params["status"] = "building"
        params["distro"], params["release"], params["target"], params["subtarget"] = imagebuilder
        requests.post(self.config.get("server") + "/worker/add_skill", json=params)

    def add_imagebuilder(self):
        self.log.info("adding imagebuilder")
        ir = requests.post(self.config.get("server") + "/worker/needed").text
        print("ir", ir)

        self.log.info("found worker_needed %s", ir)
        if ir in self.imagebuilders:
            self.log.info("already handels imagebuilder")
            return

        if ir != "":
            self.distro, self.release, self.target, self.subtarget = ir.split("/")

            self.log.info("worker serves %s %s %s %s", self.distro, self.release, self.target, self.subtarget)
            imagebuilder = ImageBuilder(self.distro, str(self.release), self.target, self.subtarget)
            self.log.info("initializing imagebuilder")
            if imagebuilder.run():
                self.log.info("register imagebuilder")
                self.worker_add_skill(imagebuilder.as_array())
                self.imagebuilders.add(ir)
                self.log.info("imagebuilder initialzed")
            else:
                # manage failures
                # add in skill status
                pass
            print("yyy", self.imagebuilders)
            self.log.info("added imagebuilder")

    def destroy(self, signal=None, frame=None):
        self.log.info("destroy worker %s", self.worker_id)
        requests.post(self.config.get("server") + "/worker/destroy", json={"worker_id": self.worker_id})
        exit(0)

    def run(self):
        self.log.info("register worker")
        self.worker_register()
        self.log.debug("setting up gnupg")
        #setup_gnupg()
        while True:
            self.log.debug("severing %s", self.imagebuilders)
            build_job_request = None
            print(self.imagebuilders)
            print("build request")
            for imagebuilder in self.imagebuilders:
                params = {}
                params["distro"], params["release"], params["target"], params["subtarget"] = imagebuilder.split("/")

                build_job_request = requests.post(self.config.get("server") + "/worker/build_job", json=params).json()
                if build_job_request:
                    break


            if build_job_request:
                self.log.debug("found build job")
                self.last_build_id = build_job_request[0]
                image = Image(self.worker_id, *build_job_request[2:9])
                self.log.debug(image.as_array())
                if not image.build():
                    self.log.warn("build failed for %s", image.as_array())
            else:
                # heartbeat should be more less than 5 seconds
                if len(self.imagebuilders) < MAX_TARGETS or MAX_TARGETS == 0:
                    self.add_imagebuilder()
                self.heartbeat()
                time.sleep(5)

    def heartbeat(self):
        requests.post(self.config.get("server") + "/worker/hearbeat", json={"worker_id": self.worker_id})

class Image(ImageMeta):
    def __init__(self, worker_id, distro, release, target, subtarget, profile, packages=None):
        super().__init__(distro, release, target, subtarget, profile, packages.split(" "))
        self.worker_id = worker_id

    def filename_rename(self, content):
        content_output = content.replace("lede", self.distro)
        content_output = content_output.replace(self.imagebuilder.imagebuilder_release, self.release)
        content_output = content_output.replace(self.request_hash, self.manifest_hash)
        return content_output

    def build(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)

        self.log.info("use imagebuilder %s", self.imagebuilder.path)


        with tempfile.TemporaryDirectory(dir=get_folder("tempdir")) as self.build_path:
            # only add manifest hash if special packages
            extra_image_name_array = []
            if not self.vanilla:
                extra_image_name_array.append(self.request_hash)

            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            cmdline.append('PROFILE=%s' % self.profile)
#            if self.network_profile:
#                cmdline.append('FILES=%s' % self.network_profile_path)
            extra_image_name = "-".join(extra_image_name_array)
            self.log.debug("extra_image_name %s", extra_image_name)
            cmdline.append('EXTRA_IMAGE_NAME=%s' % extra_image_name)
            if not self.vanilla:
                self.diff_packages()
            cmdline.append('PACKAGES=%s' % ' '.join(self.packages))
            cmdline.append('BIN_DIR=%s' % self.build_path)

            self.log.info("start build: %s", " ".join(cmdline))

            env = os.environ.copy()

            build_start = datetime.now()
            proc = subprocess.Popen(
                cmdline,
                cwd=self.imagebuilder.path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT,
                env=env
            )

            output, erros = proc.communicate()
            build_end = datetime.now()
            self.build_seconds = int((build_end - build_start).total_seconds())
            self.build_log = output.decode("utf-8")
            returnCode = proc.returncode
            if returnCode == 0:
                self.log.info("build successfull")
                self.manifest_hash = hashlib.sha256(open(glob.glob(os.path.join(self.build_path, '*.manifest'))[0],'rb').read()).hexdigest()[0:15]
                self.parse_manifest()
                self.image_hash = get_hash(" ".join(self.as_array_build()), 15)

                path_array = [get_folder("downloaddir"), self.distro, self.release, self.target, self.subtarget, self.profile]
                if not self.vanilla:
                    path_array.append(self.manifest_hash)
                else:
                    path_array.append("vanilla")

                self.store_path = os.path.join(*path_array)
                self.store_path = "/tmp/store_path"
                create_folder(self.store_path)

                with ZipFile(os.path.join(self.store_path, self.request_hash + ".zip"), 'w') as archive:
                    for filename in os.listdir(self.build_path):
                        if filename == "sha256sums":
                            with open(os.path.join(self.build_path, filename), 'r+') as sums:
                                content = sums.read()
                                sums.seek(0)
                                sums.write(self.filename_rename(content))
                                sums.truncate()
                            if sign_file(os.path.join(self.build_path, "sha256sums")):
                                self.log.info("sha265sums sign successfull")
                                archive.write(os.path.join(self.build_path, "sha256sums.sig"), arcname="sha256sums.sig")

#                        filename_output = os.path.join(self.store_path, self.filename_rename(filename))
                        self.log.info("add file %s", filename)
                        archive.write(os.path.join(self.build_path, filename), arcname=self.filename_rename(filename))

                sign_file(os.path.join(self.store_path, self.request_hash + ".zip"))

                sysupgrade_files = [ "*-squashfs-sysupgrade.bin", "*-squashfs-sysupgrade.tar",
                    "*-squashfs.trx", "*-squashfs.chk", "*-squashfs.bin",
                    "*-squashfs-sdcard.img.gz", "*-combined-squashfs*"]

                sysupgrade = None


                for sysupgrade_file in sysupgrade_files:
                    if not sysupgrade:
                        sysupgrade = glob.glob(os.path.join(self.store_path, sysupgrade_file))
                    else:
                        break

                params = {}
                params["image_hash"] = self.image_hash
                params["distro"], params["release"], params["target"], params["subtarget"], params["profile"], params["manifest_hash"] = self.as_array_build()
                params["vanilla"] = self.vanilla
                params["build_seconds"] = self.build_seconds
                params["sysupgrade_suffix"] = ""
                params["subtarget_in_name"] = ""
                params["profile_in_name"] = ""

                if not sysupgrade:
                    self.log.debug("sysupgrade not found")
                    if self.build_log.find("too big") != -1:
                        self.log.warning("created image was to big")
                        self.store_log(os.path.join(get_folder("downloaddir"), "faillogs/request-{}".format(self.request_hash)))
                        requests.post(self.config.get("server") + "/worker/request_status", json={"request_hash": self.request_hash, "status": "imagesize_fail"})
                        return False
                    else:
                        self.profile_in_name = None
                        self.subtarget_in_name = None
                        self.sysupgrade_suffix = ""
                        self.build_status = "no_sysupgrade"
                else:
                    self.path = sysupgrade[0]
                    sysupgrade_image = os.path.basename(self.path)

                    self.subtarget_in_name = self.subtarget in sysupgrade_image
                    self.profile_in_name = self.profile in sysupgrade_image

                    # ath25/generic/generic results in lede-17.01.4-ath25-generic-squashfs-sysupgrade...
                    if (self.profile == self.subtarget and
                            "{}-{}".format(self.subtarget, self.profile) not in sysupgrade_image):
                        self.subtarget_in_name = False

                    name_array = [self.distro]

                    # snapshot build are no release
                    if self.release != "snapshot":
                        name_array.append(self.release)

                    if not self.vanilla:
                        name_array.append(self.manifest_hash)

                    name_array.append(self.target)

                    if self.subtarget_in_name:
                        name_array.append(self.subtarget)

                    if self.profile_in_name:
                        name_array.append(self.profile)

                    self.name = "-".join(name_array)

                    self.sysupgrade_suffix = sysupgrade_image.replace(self.name + "-", "")
                    self.build_status = "created"

                    self.store_log(os.path.join(self.store_path, "build-{}".format(self.image_hash)))

                    self.log.debug("add image: {} {} {} {} {}".format(
                        self.image_hash,
                        self.as_array_build(),
                        self.sysupgrade_suffix,
                        self.subtarget_in_name,
                        self.profile_in_name,
                        self.vanilla,
                        self.build_seconds))

                    params["sysupgrade_suffix"] = self.sysupgrade_suffix
                    params["subtarget_in_name"] = self.subtarget_in_name
                    params["profile_in_name"] = self.profile_in_name

                requests.post(self.config.get("server") + "/worker/add_image", json=params)
                requests.post(self.config.get("server") + "/worker/build_done", json={"image_hash": self.image_hash, "request_hash": self.request_hash, "status": self.build_status})
                self.upload_image()
                return True
            else:
                self.log.info("build failed")
                requests.post(self.config.get("server") + "/worker/request_status", json={"request_hash": self.request_hash, "status": "build_fail"})
                self.store_log(os.path.join(get_folder("downloaddir"), "faillogs/request-{}".format(self.request_hash)))
                return False

    def store_log(self, path):
        self.log.debug("write log to %s", path)
        log_file = open(path + ".log", "a")
        log_file.writelines(self.build_log)

    def diff_packages(self):
        profile_packages = self.vanilla_packages
        for package in self.packages:
            if package in profile_packages:
                profile_packages.remove(package)
        for remove_package in profile_packages:
            self.packages.append("-" + remove_package)

    def parse_manifest(self):
        manifest_pattern = r"(.+) - (.+)\n"
        with open(glob.glob(os.path.join(self.build_path, '*.manifest'))[0], "r") as manifest_file:
            manifest_packages = dict(re.findall(manifest_pattern, manifest_file.read()))
            requests.post(self.config.get("server") + "/worker/add_manifest", json={"manifest_hash": self.manifest_hash, "manifest_packages": manifest_packages})

    def upload_image(self):
        url = os.path.join(self.config.get("update_server"), "upload-image")
        archive_file = os.path.join(self.store_path, self.request_hash + ".zip")
        data = {
                "request_hash": self.request_hash,
                "worker_id": self.worker_id,
                "image_hash": self.image_hash,
                }
        files = {
                'archive': open(archive_file, 'rb'),
                'signature': open(archive_file + ".sig", 'rb')
                }
        requests.post(self.config.get("server") + "/worker/upload", data=data, files=files)

    # check if image exists
    def created(self):
        return os.path.exists(self.path)
