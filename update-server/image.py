import tarfile
from config import Config
from database import Database
from imagebuilder import ImageBuilder
from util import create_folder,get_hash
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
    def __init__(self, distro, version, target, subtarget, profile, packages, network_profile=""):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.config = Config()
        self.distro = distro.lower()
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.profile = profile

        if type(packages) is str:
            self.packages = packages.split(" ")
        else:
            self.packages = packages

        self.check_network_profile(network_profile)
        self._set_path()

    def run(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.version, self.target, self.subtarget)
        if not self.imagebuilder.created():
            self.log.debug("download imagebuilder")
            self.imagebuilder.setup()

        self.imagebuilder.run()

        self.log.info("use imagebuilder at %s", self.imagebuilder.path)

        self.diff_packages()

        build_path = os.path.dirname(self.path)
        with tempfile.TemporaryDirectory() as build_path:
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

                self.log.info("build successfull")
                self.generate_checksum()
                return True
            else:
                print(output.decode('utf-8'))
                self.log.info("build failed")
                return False

    def generate_checksum(self):
        checksum = hashlib.md5(open(self.path,'rb').read()).hexdigest()
        self.database.set_checksum(self.as_array(), checksum)

    def _set_path(self):
        self.pkg_hash = self.get_pkg_hash()

        # using lede naming convention
        path_array = [self.distro, self.version, self.pkg_hash]

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
        self.path = os.path.join("download", self.distro, self.version, self.target, self.subtarget, self.name)

    def as_array(self):
        array = [self.distro, self.version, self.target, self.subtarget, self.profile, self.pkg_hash,  self.network_profile]
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
            return (self.path)
    
    # generate a hash of the installed packages
    def get_pkg_hash(self):
        # sort list and remove duplicates
        self.packages = sorted(list(set(self.packages)))

        package_hash = get_hash(" ".join(self.packages), 12)
        self.database.insert_hash(package_hash, self.packages)
        return package_hash

    # builds the image with the specific packages at output path

    # add network profile in image
    def check_network_profile(self, network_profile):
        if network_profile:
            network_profile_path = os.path.join(self.config.get("network_profile_folder"), network_profile) + "/"
            self.network_profile = network_profile
            self.network_profile_path = network_profile_path
        else:
            self.network_profile = ""

    # check if image exists
    def created(self):
        return os.path.exists(self.path)
