from util import create_folder
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
import subprocess

logging.basicConfig(level=logging.DEBUG)
root_dir = "/home/a/src/gsoc/update-server/"

class ImageBuilder():
    def __init__(self, distro, version, target, subtarget):
        self.distro = distro
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.name = "-".join([self.distro, "imagebuilder", self.version, self.target, self.subtarget])
        self.name += ".Linux-x86_64"
        self.path = os.path.join("imagebuilder", self.distro, self.version, self.target, self.subtarget, self.name)
        if not os.path.exists(os.path.join(self.path, "Makefile")):
            logging.info("downloading imagebuilder %s", self.name)
            self.download()


        self.pkg_arch = self.parse_packages_arch()
        logging.debug("found package arch %s", self.pkg_arch)
        self.add_custom_repositories()
        logging.info("initialized imagebuilder %s", self.name)

    def parse_packages_arch(self):
        with open(os.path.join(self.path, ".config"), "r") as config:
            for line in config:
                if line.startswith("CONFIG_TARGET_ARCH_PACKAGES"):
                    return re.match(r'.*"(.+)"', line).group(1)

    def add_custom_repositories(self):
        logging.info("adding custom repositories")
        with open(os.path.join(self.path, "repositories.conf"), "w") as repositories:
            with open(os.path.join(root_dir, "repositories.conf"), "r") as custom_repositories:
                custom_repositories = custom_repositories.read()
                custom_repositories = re.sub(r"{{ release }}", self.version, custom_repositories)
                custom_repositories = re.sub(r"{{ target }}", self.target, custom_repositories)
                custom_repositories = re.sub(r"{{ subtarget }}", self.subtarget, custom_repositories)
                custom_repositories = re.sub(r"{{ pkg_arch }}", self.pkg_arch, custom_repositories)
                repositories.write(custom_repositories)

    def download(self): 
        ## will be read from config file later
        imagebuilder_url = "http://downloads.lede-project.org/releases/"
        ## /tmp
        create_folder(os.path.dirname(self.path))
        imagebuilder_url_path = os.path.join(self.version, "targets", self.target, self.subtarget, self.name)
        with tempfile.TemporaryDirectory() as tar_folder:
            logging.info("downloading %s", imagebuilder_url_path)
            tar_path = os.path.join(tar_folder, "imagebuilder.tar.xz")
            full_url = os.path.join(imagebuilder_url, imagebuilder_url_path)
            full_url += ".tar.xz"
            urllib.request.urlretrieve(full_url, tar_path)
            tar = tarfile.open(tar_path)
            tar.extractall(path=tar_folder)
            tar.close()
            shutil.move(os.path.join(tar_folder, self.name), self.path)

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
            default_packages_pattern = r"\n?.*\nDefault Packages: (.+)\n"
            default_packages = re.match(default_packages_pattern, output, re.M).group(1)
            profiles_pattern = r"(.+):\n    (.+)\n    Packages: (.*)\n"
            profiles = re.findall(profiles_pattern, output)
            if not profiles:
                profiles = []
#            print(output)
            return(default_packages, profiles)
        else:
            logging.error("could not receive profiles of %s/%s", self.target, self.subtarget)


    def parse_packages(self):
        cmdline = ['make', 'package_list']
        logging.info("receive packages for %s/%s", self.target, self.subtarget)

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
            packages_pattern = r"(.+) (.+) (\d+)"
            packages = re.findall(packages_pattern, output, re.M)
#            print(output)
            return(packages)
        else:
            logging.error("could not receive packages of %s/%s", self.target, self.subtarget)

if __name__ == "__main__":
    database = Database()
    logging.info("started logger")
#    imagebuilder_old = ImageBuilder("lede", "17.01.1", "ar71xx", "generic")
    imagebuilder_x86 = ImageBuilder("lede", "17.01.1", "x86", "64")
    profiles_data = imagebuilder_x86.parse_profiles()
    packages = imagebuilder_x86.parse_packages()
    print("found %i profiles " % len(profiles_data[1]))
    print("found %i packages " % len(packages))
    database.insert_profiles(imagebuilder_x86.target, imagebuilder_x86.subtarget, profiles_data)
    database.insert_packages(imagebuilder_x86.target, imagebuilder_x86.subtarget, packages)

#    profiles_data = imagebuilder_old.parse_profiles()
#    packages = imagebuilder_old.parse_packages()
#    print("found %i profiles " % len(profiles_data[1]))
#    print("found %i packages " % len(packages))

#    database.insert_profiles(imagebuilder_old.target, imagebuilder_old.subtarget, profiles_data)
#    database.insert_packages(imagebuilder_old.target, imagebuilder_old.subtarget, packages)

