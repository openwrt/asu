import tarfile
from config import Config
from database import Database
from imagebuilder import ImageBuilder
from util import create_folder,get_hash,get_dir
import re
import shutil
import urllib.request
import tempfile
import logging
import hashlib
import os
import os.path
import subprocess
import threading

#self.log.basicConfig(filename="output.log")

class Image(threading.Thread):
    def __init__(self, distro, release, target, subtarget, profile, packages=None, network_profile=""):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.config = Config()
        self.distro = distro.lower()
        self.release = release
        self.target = target
        self.subtarget = subtarget
        self.profile = profile

        if not packages:
            self.packages = self.database.get_default_packages(self.distro, self.release, self.target, self.subtarget)
        elif type(packages) is str:
            self.packages = packages.split(" ")
        else:
            self.packages = packages

        self.check_network_profile(network_profile)
        self._set_path()
        self.set_image_request_hash()

    def run(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)
        self.imagebuilder.prepare_vars()

        self.log.info("use imagebuilder %s", self.imagebuilder.path)

        self.diff_packages()

        with tempfile.TemporaryDirectory(dir=get_dir("tempdir")) as build_path:
            create_folder(os.path.dirname(self.path))

            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            if self.target != "x86":
                cmdline.append('PROFILE=%s' % self.profile)
            print(self.packages)
            cmdline.append('PACKAGES=%s' % ' '.join(self.packages))
            if self.network_profile:
                self.log.debug("add network_profile %s", self.network_profile)
                cmdline.append('FILES=%s' % self.network_profile_path)
            cmdline.append('BIN_DIR=%s' % build_path)
            cmdline.append('EXTRA_IMAGE_NAME=%s' % self.pkg_hash)

            self.log.info("start build: %s", " ".join(cmdline))

            proc = subprocess.Popen(
                cmdline,
                cwd=self.imagebuilder.path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT
            )

            output, erros = proc.communicate()
            returnCode = proc.returncode
            if returnCode == 0:
                for sysupgrade in os.listdir(build_path):
                    if sysupgrade.endswith("combined-squashfs.img") or sysupgrade.endswith("sysupgrade.bin"):
                        self.log.info("move %s to %s", sysupgrade, self.path)
                        shutil.move(os.path.join(build_path, sysupgrade), self.path)

                self.done()
                return True
            else:
                print(output.decode('utf-8'))
                self.log.info("build failed")
                self.database.set_build_job_fail(self.image_request_hash)
                return False

    def done(self):
        self.log.info("build successfull")
        self.gen_checksum()
        self.gen_filesize()
        self.database.done_build_job(self.image_request_hash, self.checksum, self.filesize)


    def gen_checksum(self):
        self.checksum = hashlib.md5(open(self.path,'rb').read()).hexdigest()

    def gen_filesize(self):
        self.filesize = os.stat(self.path).st_size

    def _set_path(self):
        self.pkg_hash = self.get_pkg_hash()

        # using lede naming convention
        path_array = [self.distro, self.release, self.pkg_hash]

        if self.network_profile:
            path_array.append(self.network_profile.replace("/", "-").replace(".", "_"))
        
        path_array.extend([self.target, self.subtarget])

        if self.target != "x86":
            path_array.append(self.profile)
        ## .bin should always be fine
        path_array.append("sysupgrade.bin")
       # else:
       #     path_array.append("sysupgrade.img")

        self.name = "-".join(path_array)
        self.path = os.path.join(get_dir("downloaddir"), self.distro, self.release, self.target, self.subtarget, self.name)

    def as_array(self):
        array = [self.distro, self.release, self.target, self.subtarget, self.profile, self.pkg_hash,  self.network_profile]
        return array

    def diff_packages(self):
        default_packages = self.imagebuilder.default_packages
        for package in self.packages:
            if package in default_packages:
                default_packages.remove(package)
        for remove_package in default_packages:
            self.packages.append("-" + remove_package)

    # returns the path of the created image
    def get_sysupgrade(self):
        if not self.created():
            return None
        else:
            self.log.debug("Heureka!")
            return "/".join(self.path.split("/")[-5:])
    
    # generate a hash of the installed packages
    def get_pkg_hash(self):
        # sort list and remove duplicates
        self.packages = sorted(list(set(self.packages)))

        package_hash = get_hash(" ".join(self.packages), 12)
        self.database.insert_hash(package_hash, self.packages)
        return package_hash

    def set_image_request_hash(self):
        self.image_request_hash = get_hash(" ".join(self.as_array()), 12)

    # builds the image with the specific packages at output path

    # add network profile in image
    def check_network_profile(self, network_profile):
        self.log.debug("check network profile")
        if network_profile:
            network_profile_path = os.path.join(self.config.get("network_profile_folder"), network_profile) + "/"
            self.network_profile = network_profile
            self.network_profile_path = network_profile_path
        else:
            self.network_profile = ""

    # check if image exists
    def created(self):
        return os.path.exists(self.path)
