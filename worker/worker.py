import threading
import glob
import re
from socket import gethostname
import shutil
import json
import urllib.request
import tempfile
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
from utils.common import create_folder, get_hash, get_folder, setup_gnupg, sign_image
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
        self.database = Database()
        self.log.info("database initialized")
        self.worker_id = None
        self.imagebuilders = []

    def worker_register(self):
        self.worker_id = str(self.database.worker_register(gethostname()))

    def worker_add_skill(self, imagebuilder):
        self.database.worker_add_skill(self.worker_id, *imagebuilder, 'ready')

    def add_imagebuilder(self):
        self.log.info("adding imagebuilder")
        imagebuilder_request = None

        while not imagebuilder_request:
            imagebuilder_request = self.database.worker_needed()
            if not imagebuilder_request:
                self.heartbeat()
                time.sleep(5)
                continue

            self.log.info("found worker_needed %s", imagebuilder_request)
            for imagebuilder_setup in self.imagebuilders:
                if len(set(imagebuilder_setup).intersection(imagebuilder_request)) == 4:
                    self.log.info("already handels imagebuilder")
                    return

            self.distro, self.release, self.target, self.subtarget = imagebuilder_request
            self.log.info("worker serves %s %s %s %s", self.distro, self.release, self.target, self.subtarget)
            imagebuilder = ImageBuilder(self.distro, str(self.release), self.target, self.subtarget)
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
        setup_gnupg()
        while True:
            self.log.debug("severing %s", self.imagebuilders)
            build_job_request = None
            for imagebuilder in self.imagebuilders:
                build_job_request = self.database.get_build_job(*imagebuilder)
                if build_job_request:
                    break

            if build_job_request:
                self.log.debug("found build job")
                self.last_build_id = build_job_request[0]
                image = Image(*build_job_request[2:9])
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
        self.log.debug("heartbeat %s", self.worker_id)
        self.database.worker_heartbeat(self.worker_id)

class Image(ImageMeta):
    def __init__(self, distro, release, target, subtarget, profile, packages=None, network_profile=""):
        super().__init__(distro, release, target, subtarget, profile, packages, network_profile)

    def build(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)

        self.log.info("use imagebuilder %s", self.imagebuilder.path)


        with tempfile.TemporaryDirectory(dir=get_folder("tempdir")) as self.build_path:
            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            cmdline.append('PROFILE=%s' % self.profile)
            if self.network_profile:
                self.log.debug("add network_profile %s", self.network_profile)
                self.network_profile_packages()
                cmdline.append('FILES=%s' % self.network_profile_path)
            self.diff_packages()
            cmdline.append('PACKAGES=%s' % ' '.join(self.packages))
            cmdline.append('BIN_DIR=%s' % self.build_path)

            self.log.info("start build: %s", " ".join(cmdline))

            proc = subprocess.Popen(
                cmdline,
                cwd=self.imagebuilder.path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT
            )

            self.log_output, erros = proc.communicate()
            returnCode = proc.returncode
            if returnCode == 0:
                self.log.info("build successfull")
                self.manifest_hash = hashlib.sha256(open(glob.glob(os.path.join(self.build_path, '*.manifest'))[0],'rb').read()).hexdigest()[0:15]
                self.manifest_id = self.database.add_manifest(self.manifest_hash)
                self.parse_manifest()
                self.image_hash = get_hash(" ".join(self.as_array_build()), 15)
                self.set_path()
                create_folder(os.path.dirname(self.path))

                self.store_log(self.path)

                if not os.path.exists(self.path):
                    sysupgrade = glob.glob(os.path.join(self.build_path, '*sysupgrade.bin'))
                    if not sysupgrade:
                        sysupgrade = glob.glob(os.path.join(self.build_path, '*combined-squashfs.img'))
                        if not sysupgrade:
                            sysupgrade = glob.glob(os.path.join(self.build_path, '*combined-squashfs.img.gz'))
                            if not sysupgrade:
                                sysupgrade = glob.glob(os.path.join(self.build_path, '*squashfs-sysupgrade.tar')) # ipq806x/EA8500

                    self.log.debug(glob.glob(os.path.join(self.build_path, '*')))

                    if not sysupgrade:
                        self.log.error("created image was to big")
                        self.database.set_image_requests_status(self.request_hash, 'imagesize_fail')
                        return False

                    self.log.info("move %s to %s", sysupgrade, self.path)
                    shutil.move(sysupgrade[0], self.path)
                    if self.config.get("sign_images"):
                        if sign_image(self.path):
                            self.log.info("signed %s", self.path)
                        else:
                            self.database.set_image_requests_status(self.request_hash, 'signing_fail')
                            return False
                    self.gen_checksum()
                    self.gen_filesize()
                    self.database.add_image(self.image_hash, self.as_array_build(), self.checksum, self.filesize)
                else:
                    self.log.info("image already created")
                self.database.done_build_job(self.request_hash, self.image_hash)
                return True
            else:
                self.log.info("build failed")
                self.database.set_image_requests_status(self.request_hash, 'build_fail')
                self.store_log(os.path.join(get_folder("downloaddir"), "faillogs", self.request_hash))
                return False

    def store_log(self, path):
        self.log.debug("write log to %s", path)
        log_file = open(path + ".log", "a")
        log_file.writelines(json.dumps(self.as_array(), indent=4, sort_keys=True))
        log_file.write("\n\n")
        log_file.writelines(self.log_output.decode('utf-8'))

    def gen_checksum(self):
        self.checksum = hashlib.md5(open(self.path,'rb').read()).hexdigest()
        self.log.debug("got md5sum %s for %s", self.checksum, self.path)

    def gen_filesize(self):
        self.filesize = os.stat(self.path).st_size

    def set_path(self):
        # using lede naming convention
        path_array = [self.distro, self.release, self.manifest_hash]

        if self.network_profile:
            path_array.append(self.network_profile.replace("/", "-").replace(".", "_"))

        path_array.extend([self.target, self.subtarget, self.profile])

        path_array.append("sysupgrade.bin")

        self.name = "-".join(path_array)
        self.path = os.path.join(get_folder("downloaddir"), self.distro, self.release, self.target, self.subtarget, self.profile, self.name)

    def network_profile_packages(self):
        extra_packages = os.path.join(self.network_profile_path, 'PACKAGES')
        if os.path.exists(extra_packages):
            with open(extra_packages, "r") as extra_packages_file:
                self.packages.extend(extra_packages_file.read().split())

    def diff_packages(self):
        profile_packages = self.database.get_image_packages(self.distro, self.release, self.target, self.subtarget, self.profile)
        for package in self.packages:
            if package in profile_packages:
                profile_packages.remove(package)
        for remove_package in profile_packages:
            self.packages.append("-" + remove_package)

    def parse_manifest(self):
        manifest_pattern = r"(.+) - (.+)\n"
        with open(glob.glob(os.path.join(self.build_path, '*.manifest'))[0], "r") as manifest_file:
            manifest_packages = re.findall(manifest_pattern, manifest_file.read())
            self.database.add_manifest_packages(self.manifest_hash, manifest_packages)

    # check if image exists
    def created(self):
        return os.path.exists(self.path)
