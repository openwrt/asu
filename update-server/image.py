import tarfile
from config import Config
from database import Database
from imagebuilder import ImageBuilder
from util import create_folder
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
    # distro
    # version
    # target
    # subtarget
    # profile
    # packages
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.config = Config()

    def run(self):
        imagebuilder_path = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        self.imagebuilder = ImageBuilder(self.distro, self.version, self.target, self.subtarget)
        if not self.imagebuilder.created:
            self.imagebuilder.download()

        self.imagebuilder.run()

        self.log.info("use imagebuilder at %s", self.imagebuilder.path)

        self.diff_packages()

        build_path = os.path.dirname(self.path)
        with tempfile.TemporaryDirectory() as build_path:
            create_folder(os.path.dirname(self.path))

            cmdline = ['make', 'image', "-j", str(os.cpu_count())]
            if self.target != "x86":
                cmdline.append('PROFILE=%s' % self.profile)
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
                        self.log.info("move %s to %s", sysupgrade, (self.path + "-sysupgrade.bin"))
                        shutil.move(os.path.join(build_path, sysupgrade), (self.path + "-sysupgrade.bin"))

                    if sysupgrade.endswith("factory.bin"):
                        self.log.info("move %s to %s", sysupgrade, (self.path + "-factory.bin"))
                        shutil.move(os.path.join(build_path, sysupgrade), (self.path + "-factory.bin"))

                self.log.info("build successfull")
            else:
                print(output.decode('utf-8'))
                self.log.info("build failed")

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
       #     path_array.append("sysupgrade.bin")
       # else:
       #     path_array.append("sysupgrade.img")

        self.name = "-".join(path_array)
        self.path = os.path.join("download", self.distro, self.version, self.target, self.subtarget, self.name)

    def request_variables(self, distro, version, target, subtarget, profile, packages, network_profile=None):
        self.distro = distro.lower()
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.profile = profile
        self.packages = packages
        self.check_network_profile(network_profile)
        self._set_path()

    def request_params(self, params):
        self.distro = params["distro"].lower()
        self.version = params["version"]
        self.target = params["target"]
        self.subtarget = params["subtarget"]
        self.profile = params["profile"]
        self.packages = params["packages"]
        self._set_path()

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
            return (self.path + "-sysupgrade.bin")
    
    def get_factory(self):
        if not self.created():
            return None
        else:
            self.log.debug("Heureka!")
            return (self.path + "-factory.bin")

    # generate a hash of the installed packages
    def get_pkg_hash(self):
        # sort list and remove duplicates
        self.packages = sorted(list(set(self.packages)))

        h = hashlib.sha256()
        h.update(bytes(" ".join(self.packages), 'utf-8'))
        package_hash = h.hexdigest()[:12]
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
            self.network_profile = None

    # check if image exists
    def created(self):
        return os.path.exists(self.path + "-sysupgrade.bin")

# todo move stuff to tmp and only move sysupgrade file
# usign für python ansehen

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # with some usefull tools"
    packages = ['base-files', 'libc', 'libgcc', 'busybox', 'dropbear', 'mtd', 'uci', 'opkg', 'netifd', 'fstools', 'uclient-fetch', 'logd', 'partx-utils', 'mkf2fs', 'e2fsprogs', 'kmod-button-hotplug', 'kmod-e1000e', 'kmod-e1000', 'kmod-r8169', 'kmod-igb', 'dnsmasq', 'iptables', 'ip6tables', 'firewall', 'odhcpd', 'odhcp6c']

    packages.extend(["vim", "vim", "luci", "iperf", "wavemon", "syslog-ng"])

    packages.extend(["vim", "attended-sysupgrade", "luci", "luci2-io-helper"])

    network_profile = "zweieck.lan/generic"
    # builds libremesh
    #packages =  ["vim", "tmux", "screen", "attended-sysupgrade", "luci", "lime-full", "-ppp", "-dnsmasq", "-ppp-mod-pppoe", "-6relayd", "-odhcp6c", "-odhcpd", "-firewall"]

#    image_ar71 = Image()
#    image_ar71.request_variables("lede", "17.01.1", "ar71xx", "generic", "ubnt-loco-m-xw", packages)
#    image_ar71.get()
    image_x86 = Image()
    image_x86.request_variables("lede", "17.01.0", "x86", "64", "", packages)
    if not image_x86.created():
        image_x86.run()
    image_x86.get_sysupgrade()
#    image_x86_2 = Image()
#    image_x86_2.request_variables("lede", "17.01.1", "x86", "64", "", packages)
#    image_x86_2.get()
#    image_x86.request_variables("lede", "17.01.0", "ar71xx", "generic", "", packages)
#    imagebuilder_old = ImageBuilder("lede", "17.01.0", "ar71xx", "generic")
#    imagebuilder_x86 = ImageBuilder("lede", "17.01.1", "x86", "64")
#    profiles_data = imagebuilder_x86.parse_profiles()
#    packages = imagebuilder_x86.parse_packages()
#    print("found %i profiles " % len(profiles_data[1]))
#    print("found %i packages " % len(packages))
#    database.insert_profiles(imagebuilder_x86.target, imagebuilder_x86.subtarget, profiles_data)
#    database.insert_packages(imagebuilder_x86.target, imagebuilder_x86.subtarget, packages)
#
#    profiles_data = imagebuilder_old.parse_profiles()
#    packages = imagebuilder_old.parse_packages()
#    print("found %i profiles " % len(profiles_data[1]))
#    print("found %i packages " % len(packages))
#
#    database.insert_profiles(imagebuilder_old.target, imagebuilder_old.subtarget, profiles_data)
#    database.insert_packages(imagebuilder_old.target, imagebuilder_old.subtarget, packages)
#
