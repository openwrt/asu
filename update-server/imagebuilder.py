from os import walk
from util import create_folder, get_statuscode, get_latest_release
import logging
import tarfile
from database import Database
import re
import shutil
import urllib.request
import tempfile
import logging
import hashlib
import os
import os.path
from config import Config
import threading
import subprocess

class ImageBuilder(threading.Thread):
    def __init__(self, distro, version, target, subtarget):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.config = Config()
        self.distro = distro
        self.version = version
        self.release = version
        self.imagebuilder_release = version
        if self.config.get("snapshots") and version == "snapshot":
            self.imagebuilder_release = "snapshots"
        elif distro != "lede":
            self.imagebuilder_release = get_latest_release("lede")
        self.target = target
        self.subtarget = subtarget
        self.root = os.path.dirname(os.path.realpath(__file__))
        self.path = os.path.join("imagebuilder", self.distro, self.version, self.target, self.subtarget)
    
    def prepare_vars(self):
        self.pkg_arch = self.parse_packages_arch()
        self.default_packages = self.database.get_default_packages(self.distro, self.release, self.target, self.subtarget)
        self.available_packages= self.database.get_available_packages(self.distro, self.release, self.target, self.subtarget)
        logging.debug("found package arch %s", self.pkg_arch)


    # this is ugly due to the fact that some imagebuilders have -generic
    # removed in their download names, more generic apporach needed
    def created(self):
        if os.path.exists(os.path.join(self.path, "Makefile")):
            return True

    def parse_packages_arch(self):
        logging.debug("parse_packages_arch")
        with open(os.path.join(self.path, ".config"), "r") as config:
            for line in config:
                if line.startswith("CONFIG_TARGET_ARCH_PACKAGES"):
                    return re.match(r'.*"(.+)"', line).group(1)

    def add_custom_repositories(self):
        self.pkg_arch = self.parse_packages_arch()
        self.log.info("adding custom repositories")
        custom_repositories = None
        custom_repositories_path = os.path.join("distributions", self.distro, "repositories.conf")
        if os.path.exists(custom_repositories_path):
            with open(custom_repositories_path, "r") as custom_repositories_distro:
                custom_repositories = self.fill_repositories_template(custom_repositories_distro.read())
        elif os.path.exists("repositories.conf.default"):
            with open("repositories.conf.default", "r") as custom_repositories_default:
                custom_repositories = self.fill_repositories_template(custom_repositories_default.read())
        if custom_repositories:
            with open(os.path.join(self.path, "repositories.conf"), "w") as repositories:
                repositories.write(custom_repositories)

    def fill_repositories_template(self, custom_repositories):
        custom_repositories = re.sub(r"{{ distro }}", self.distro, custom_repositories)
        custom_repositories = re.sub(r"{{ imagebuilder_release }}", self.imagebuilder_release, custom_repositories)
        custom_repositories = re.sub(r"{{ release }}", self.release, custom_repositories)
        custom_repositories = re.sub(r"{{ target }}", self.target, custom_repositories)
        custom_repositories = re.sub(r"{{ subtarget }}", self.subtarget, custom_repositories)
        custom_repositories = re.sub(r"{{ pkg_arch }}", self.pkg_arch, custom_repositories)
        if self.imagebuilder_release is "snapshots":
            custom_repositories = re.sub(r"/releases/snapshots", "/snapshots", custom_repositories)
        return custom_repositories

    def add_custom_makefile(self):
        self.log.info("adding custom Makefile")
        shutil.copyfile(os.path.join(self.root, "Makefile"), os.path.join(self.path, "Makefile"))

    def download_url(self, remove_subtarget=False):
        name_array = ["lede-imagebuilder"]
        # some imagebuilders have -generic removed
        self.log.warn(self.imagebuilder_release)
        if not self.imagebuilder_release is "snapshots":
            name_array.append(self.imagebuilder_release)
        name_array.append(self.target)
        if not remove_subtarget:
            name_array.append(self.subtarget)
        name = "-".join(name_array)
        name += ".Linux-x86_64.tar.xz"
        self.log.warning(os.path.join(self.config.get("imagebuilder_snapshots_url"), "targets", self.target, self.subtarget, name))

        if self.imagebuilder_release == "snapshots":
            return os.path.join(self.config.get("imagebuilder_snapshots_url"), "targets", self.target, self.subtarget, name)
        return os.path.join(self.config.get("imagebuilder_url"), self.imagebuilder_release, "targets", self.target, self.subtarget, name)

    def run(self): 
        self.log.info("downloading imagebuilder %s", self.path)
        if not self.created():
            if get_statuscode(self.download_url()) != 404:
                self.download(self.download_url())
            else:
                # this is only due to arm64 missing -generic in filename
                if get_statuscode(self.download_url(True)) != 404:
                    self.log.debug("remove -generic from url")
                    self.download(self.download_url(True))
                else:
                    self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'download_fail')
                    return False
        self.add_custom_repositories()
        self.add_custom_makefile()
        self.parse_profiles()
        self.parse_packages()
        self.log.info("initialized imagebuilder %s", self.path)
        self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'ready')
        return True

    def download(self, url):
        with tempfile.TemporaryDirectory() as tar_folder:
            create_folder(self.path)
            tar_path = os.path.join(tar_folder, "imagebuilder.tar.xz")
            self.log.info("downloading url %s", url)
            urllib.request.urlretrieve(url, tar_path)
            tar = tarfile.open(tar_path)
            tar.extractall(path=tar_folder)
            for (dirpath, dirnames, filenames) in walk(os.path.join(tar_folder, tar.getnames()[0])):
                for dirname in dirnames:
                    shutil.move(os.path.join(dirpath, dirname), self.path)
                for filename in filenames:
                    shutil.move(os.path.join(dirpath, filename), self.path)
                break
            tar.close()
                
            return True
        return False

    def parse_profiles(self):
        cmdline = ['make', 'info']
        self.log.info("receive profiles for %s/%s", self.target, self.subtarget)

        proc = subprocess.Popen(
            cmdline,
            cwd=self.path,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )

        output, erros = proc.communicate()
        returnCode = proc.returncode
        output = output.decode('utf-8')
        if returnCode == 0:
            default_packages_pattern = r"(.*\n)*Default Packages: (.+)\n"
            default_packages = re.match(default_packages_pattern, output, re.M).group(2)
            logging.debug("default packages: %s", default_packages)
            profiles_pattern = r"(.+):\n    (.+)\n    Packages: (.*)\n"
            profiles = re.findall(profiles_pattern, output)
            if not profiles:
                profiles = []
#            print(output)
            self.database.insert_profiles(self.distro, self.release, self.target, self.subtarget, (default_packages, profiles))
        else:
            logging.error("could not receive profiles of %s/%s", self.target, self.subtarget)

    def parse_packages(self):
        self.log.info("receive packages for %s/%s", self.target, self.subtarget)

        cmdline = ['make', 'package_list']
        proc = subprocess.Popen(
            cmdline,
            cwd=self.path,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )

        output, erros = proc.communicate()
        returnCode = proc.returncode
        output = output.decode('utf-8')
       # print(output)
        if returnCode == 0:
            packages = re.findall(r"(.+?) - (.+?) - .*\n", output)
            self.log.info("found {} packages for {} {} {} {}".format(len(packages), self.distro, self.release, self.target, self.subtarget))
            self.database.insert_packages(self.distro, self.release, self.target, self.subtarget, packages)
        else:
            print(output)
            self.log.warning("could not receive packages of %s/%s", self.target, self.subtarget)
