import logging
import os.path

from utils.common import create_folder,get_hash,get_dir
from utils.config import Config
from utils.database import Database

class ImageMeta():
    def __init__(self, distro, release, target, subtarget, profile, packages=None, network_profile=""):
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
        self.set_request_hash()

    def as_array_build(self):
        array = [self.distro, self.release, self.target, self.subtarget, self.profile, self.manifest_hash, self.network_profile]
        return array

    def as_array(self):
        self.pkg_hash = self.get_pkg_hash()
        array = [self.distro, self.release, self.target, self.subtarget, self.profile, self.pkg_hash, self.network_profile]
        return array

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
