from util import create_folder, get_statuscode
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
import subprocess

class ImageBuilder():
    def __init__(self, distro, version, target, subtarget):
        self.database = Database()
        self.config = Config()
        self.distro = distro
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.root = os.path.dirname(os.path.realpath(__file__))
        self.name = "-".join([self.distro, "imagebuilder", self.version, self.target, self.subtarget])
        self.name += ".Linux-x86_64"
        self.path = os.path.join("imagebuilder", self.distro, self.version, self.target, self.subtarget, self.name)

    def run(self):
        self.default_packages = self.database.get_default_packages(self.target, self.subtarget)
        if not self.default_packages:
            self.parse_profiles()
            self.default_packages = self.database.get_default_packages(self.target, self.subtarget)

        self.available_packages= self.database.get_available_packages(self.target, self.subtarget)
        if not self.available_packages:
            self.parse_packages()
            self.available_packages= self.database.get_available_packages(self.target, self.subtarget)

        self.pkg_arch = self.parse_packages_arch()
        logging.debug("found package arch %s", self.pkg_arch)
        self.add_custom_repositories()
        self.add_custom_makefile()
        logging.info("initialized imagebuilder %s", self.name)

    def created(self):
        return os.path.exists(os.path.join(self.path, "Makefile"))

    def parse_packages_arch(self):
        logging.debug("parse_packages_arch")
        with open(os.path.join(self.path, ".config"), "r") as config:
            for line in config:
                if line.startswith("CONFIG_TARGET_ARCH_PACKAGES"):
                    return re.match(r'.*"(.+)"', line).group(1)

    def add_custom_repositories(self):
        logging.info("adding custom repositories")
        with open(os.path.join(self.path, "repositories.conf"), "w") as repositories:
            with open(os.path.join(self.root, "repositories.conf"), "r") as custom_repositories:
                custom_repositories = custom_repositories.read()
                custom_repositories = re.sub(r"{{ release }}", self.version, custom_repositories)
                custom_repositories = re.sub(r"{{ target }}", self.target, custom_repositories)
                custom_repositories = re.sub(r"{{ subtarget }}", self.subtarget, custom_repositories)
                custom_repositories = re.sub(r"{{ pkg_arch }}", self.pkg_arch, custom_repositories)
                repositories.write(custom_repositories)

    def add_custom_makefile(self):
        logging.info("adding custom Makefile")
        shutil.copyfile(os.path.join(self.root, "Makefile"), os.path.join(self.path, "Makefile"))

    def download(self): 
        ## will be read from config file later
        logging.info("downloading imagebuilder %s", self.name)
        imagebuilder_url = self.config.get("imagebuilder_url")
        create_folder(os.path.dirname(self.path))
        imagebuilder_url_path = os.path.join(self.version, "targets", self.target, self.subtarget, self.name)
        tar_path = os.path.join(tar_folder, "imagebuilder.tar.xz")
        full_url = os.path.join(imagebuilder_url, imagebuilder_url_path)
        full_url += ".tar.xz"
        
        if not get_statuscode(full_url) == 400:
            with tempfile.TemporaryDirectory() as tar_folder:
                logging.info("downloading %s", full_url)
                urllib.request.urlretrieve(full_url, tar_path)
                tar = tarfile.open(tar_path)
                tar.extractall(path=tar_folder)
                tar.close()
                shutil.move(os.path.join(tar_folder, self.name), self.path)
                return True
        return False

    def parse_profiles(self):
        cmdline = ['make', 'info']
        logging.info("receive profiles for %s/%s", self.target, self.subtarget)

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
            self.database.insert_profiles(self.target, self.subtarget, (default_packages, profiles))
        else:
            logging.error("could not receive profiles of %s/%s", self.target, self.subtarget)


    def parse_packages(self):
        logging.info("receive packages for %s/%s", self.target, self.subtarget)

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
            self.database.insert_packages(self.target, self.subtarget, packages)
            return packages
        else:
            logging.error("could not receive packages of %s/%s", self.target, self.subtarget)
