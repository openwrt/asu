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
from utils.common import get_hash, gpg_init, gpg_recv_keys, usign_sign, usign_pubkey, usign_init
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
        self.worker_id = None
        self.imagebuilders = []
        self.auth = (self.config.get("worker"), self.config.get("password"))
        self.worker_name = gethostname()
        self.worker_address = ""
        usign_init("worker-" + self.worker_name)

    def api(self, path, data=None, json=None, files=None):
        try:
            return requests.post(self.config.get("server") + path, json=json, data=data, files=files, auth=self.auth).json()
        except ConnectionError:
           self.log.error("could not connect to server")
           exit(1)

    def worker_register(self):
        self.worker_pubkey = usign_pubkey()
        self.log.info("register worker '%s' '%s' '%s'", self.worker_name, self.worker_address, self.worker_pubkey)
        print(self.worker_pubkey)
        json = {'worker_name': gethostname(), 'worker_address': '', 'worker_pubkey': self.worker_pubkey}
        self.worker_id = str(self.api("/worker/register", json=json))

    def worker_add_skill(self, imagebuilder):
        self.database.worker_add_skill(self.worker_id, *imagebuilder, 'ready')

    def add_imagebuilder(self, distro, release, target, subtarget):
        self.log.info("adding imagebuilder")
        self.log.info("worker serves %s %s %s %s", distro, release, target, subtarget)
        imagebuilder = ImageBuilder(distro, str(release), target, subtarget)
        self.log.info("initializing imagebuilder")
        if imagebuilder.run():
            self.log.info("register imagebuilder")
            self.worker_add_skill(imagebuilder.as_array())
            self.imagebuilders.append(imagebuilder.as_array())
            self.log.info("imagebuilder initialzed")
        else:
            # manage failures
            # add in skill status
            pass
        self.log.info("added imagebuilder")

    def destroy(self, signal=None, frame=None):
        self.log.info("destroy worker %s", self.worker_id)
        self.database.worker_destroy(self.worker_id)
        sys.exit(0)

    def run(self):
        self.log.info("register worker")
        self.worker_register()
        self.log.debug("setting up gnupg")
        gpg_init()
        gpg_recv_keys()
        while True:
            self.log.debug("severing %s", self.imagebuilders)
            build_job_request = None
            for imagebuilder in self.imagebuilders:
                if ImageBuilder(*imagebuilder).created():
                    build_job_request = self.database.get_build_job(*imagebuilder)
                    if build_job_request:
                        break
                else:
                    self.add_imagebuilder(*imagebuilder)

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
                    imagebuilder_request = None
                    while not imagebuilder_request:
                        imagebuilder_request = self.database.worker_needed()
                        if not imagebuilder_request:
                            self.heartbeat()
                            time.sleep(5)
                            continue

                        self.log.info("found worker_needed %s", imagebuilder_request)
                        if not imagebuilder_request in self.imagebuilders:
                            self.add_imagebuilder(*imagebuilder_request)

                self.heartbeat()
                time.sleep(5)

    def heartbeat(self):
        self.log.debug("heartbeat %s", self.worker_id)
        self.database.worker_heartbeat(self.worker_id)

class Image(ImageMeta):
    def __init__(self, worker_id, distro, release, target, subtarget, profile, packages=None):
        self.worker_id = worker_id
        super().__init__(distro, release, target, subtarget, profile, packages.split(" "))

    def filename_rename(self, content):
        if self.release == "snapshot":
            content_output = content.replace("openwrt", self.distro)
        else:
            content_output = content.replace(self.config.get(self.distro).get("parent_distro", self.distro), self.distro)

        content_output = content_output.replace(self.imagebuilder.imagebuilder_release, self.release)
        content_output = content_output.replace(self.request_hash, self.manifest_hash)
        return content_output

    def build(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)

        self.log.info("use imagebuilder %s", self.imagebuilder.path)


        with tempfile.TemporaryDirectory(dir=self.config.get_folder("tempdir")) as self.build_path:
            already_created = False

            # only add manifest hash if special packages
            extra_image_name_array = []
            if not self.vanilla:
                extra_image_name_array.append(self.request_hash)

            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            cmdline.append('PROFILE=%s' % self.profile)

            # add server key to image
            server_keys = self.config.get("keys_public") + "/server"
            if self.config.get("sign_images") and os.path.exists(server_keys):
                cmdline.append('FILES=%s' % server_keys)

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

                path_array = [self.config.get_folder("download_folder"), self.distro, self.release, self.target, self.subtarget, self.profile]
                if not self.vanilla:
                    path_array.append(self.manifest_hash)
                else:
                    path_array.append("vanilla")

                self.store_path = os.path.join(*path_array)
                os.makedirs(self.store_path, exist_ok=True)

                self.log.debug(os.listdir(self.build_path))
                for filename in os.listdir(self.build_path):
                    if filename == "sha256sums":
                        with open(os.path.join(self.build_path, filename), 'r+') as sums:
                            content = sums.read()
                            sums.seek(0)
                            sums.write(self.filename_rename(content))
                            sums.truncate()
                    filename_output = os.path.join(self.store_path, self.filename_rename(filename))

                    self.log.info("move file %s", filename_output)
                    shutil.move(os.path.join(self.build_path, filename), filename_output)

                usign_sign(os.path.join(self.store_path, "sha256sums"))
                self.log.info("signed sha256sums")

                if not already_created or entry_missing:
                    sysupgrade_files = [ "*-squashfs-sysupgrade.bin",
                            "*-squashfs-sysupgrade.tar", "*-squashfs.trx",
                            "*-squashfs.chk", "*-squashfs.bin",
                            "*-squashfs-sdcard.img.gz", "*-combined-squashfs*",
                            "*.img.gz"]

                    sysupgrade = None

                    profile_in_sysupgrade = ""
                    if self.profile.lower() != "generic":
                        profile_in_sysupgrade = "*" + self.profile

                    for sysupgrade_file in sysupgrade_files:
                        if not sysupgrade:
                            sysupgrade = glob.glob(os.path.join(self.store_path, profile_in_sysupgrade + sysupgrade_file))
                        else:
                            break

                    if not sysupgrade:
                        self.log.debug("sysupgrade not found")
                        if self.build_log.find("too big") != -1:
                            self.log.warning("created image was to big")
                            self.store_log(os.path.join(self.config.get_folder("download_folder"), "faillogs/request-{}".format(self.request_hash)))
                            self.database.set_image_requests_status(self.request_hash, 'imagesize_fail')
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

                    self.log.debug("add image: {} {} {} {} {} {}".format(
                            self.image_hash,
                            self.as_array_build(),
                            self.worker_id,
                            self.sysupgrade_suffix,
                            self.subtarget_in_name,
                            self.profile_in_name,
                            self.vanilla,
                            self.build_seconds))
                    self.database.add_image(
                            self.image_hash,
                            *self.as_array_build(),
                            self.worker_id,
                            self.sysupgrade_suffix,
                            self.subtarget_in_name,
                            self.profile_in_name,
                            self.vanilla,
                            self.build_seconds)
                self.database.done_build_job(self.request_hash, self.image_hash, self.build_status)
                return True
            else:
                self.log.info("build failed")
                self.database.set_image_requests_status(self.request_hash, 'build_fail')
                self.store_log(os.path.join(self.config.get_folder("download_folder"), "faillogs/request-{}".format(self.request_hash)))
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
            self.database.add_manifest_packages(self.manifest_hash, manifest_packages)

    # check if image exists
    def created(self):
        return os.path.exists(self.path)
