import tarfile
import glob
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

        if not packages: # install default packages
            self.packages = self.database.get_profile_packages(self.distro, self.release, self.target, self.subtarget, self.profile)
        elif type(packages) is str:
            self.packages = packages.split(" ")
        else:
            self.packages = packages

        self.check_network_profile(network_profile)
        #self._set_path()
        self.set_request_hash()

    def run(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.release, self.target, self.subtarget)

        self.log.info("use imagebuilder %s", self.imagebuilder.path)

        self.diff_packages()

        with tempfile.TemporaryDirectory(dir=get_dir("tempdir")) as self.build_path:

            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            cmdline.append('PROFILE=%s' % self.profile)
            print(self.packages)
            cmdline.append('PACKAGES=%s' % ' '.join(self.packages))
            if self.network_profile:
                self.log.debug("add network_profile %s", self.network_profile)
                cmdline.append('FILES=%s' % self.network_profile_path)
            cmdline.append('BIN_DIR=%s' % self.build_path)
            #cmdline.append('EXTRA_IMAGE_NAME=%s' % self.manifest_hash)

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
                self.log.info("build successfull")
                self.manifest_hash = hashlib.sha256(open(glob.glob(os.path.join(self.build_path, '*.manifest'))[0],'rb').read()).hexdigest()[0:15]
                self.manifest_id = self.database.add_manifest(self.manifest_hash)
                self.parse_manifest()
                self.image_hash = get_hash(" ".join(self.as_array_build()), 15)
                self._set_path()
                create_folder(os.path.dirname(self.path))
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
                    self.gen_checksum()
                    self.gen_filesize()
                    self.database.add_image(self.image_hash, self.as_array_build(), self.checksum, self.filesize)
                else:
                    self.log.info("image already created")
                self.database.done_build_job(self.request_hash, self.image_hash)
                return True
            else:
                print(output.decode('utf-8'))
                self.log.info("build failed")
                self.database.set_build_job_fail(self.request_hash)
                return False

    def gen_checksum(self):
        self.checksum = hashlib.md5(open(self.path,'rb').read()).hexdigest()
        self.log.debug("got md5sum %s for %s", self.checksum, self.path)

    def gen_filesize(self):
        self.filesize = os.stat(self.path).st_size

    def _set_path(self):
        # using lede naming convention
        path_array = [self.distro, self.release, self.manifest_hash]

        if self.network_profile:
            path_array.append(self.network_profile.replace("/", "-").replace(".", "_"))

        path_array.extend([self.target, self.subtarget, self.profile])

        path_array.append("sysupgrade.bin")

        self.name = "-".join(path_array)
        self.path = os.path.join(get_dir("downloaddir"), self.distro, self.release, self.target, self.subtarget, self.profile, self.name)

    def as_array_build(self):
        array = [self.distro, self.release, self.target, self.subtarget, self.profile, self.manifest_hash, self.network_profile]
        return array

    def as_array(self):
        self.pkg_hash = self.get_pkg_hash()
        array = [self.distro, self.release, self.target, self.subtarget, self.profile, self.pkg_hash, self.network_profile]
        return array

    def diff_packages(self):
        profile_packages = self.database.get_profile_packages(self.distro, self.release, self.target, self.subtarget, self.profile)
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
        self.log.debug("pkg hash %s - %s", package_hash, self.packages)
        self.database.insert_hash(package_hash, self.packages)
        return package_hash

    def set_request_hash(self):
        self.request_hash = get_hash(" ".join(self.as_array()), 12)

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
