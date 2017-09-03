import logging
import tarfile
import re
import shutil
import urllib.request
import tempfile
import logging
import os
import os.path
import threading
import subprocess

from utils.common import create_folder, get_statuscode, get_latest_release, get_dir, get_root, check_signature
from utils.database import Database
from utils.config import Config

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
            self.log.debug("using snapshot imagebuilder")
            self.imagebuilder_release = "snapshots"
        elif distro != "lede":
            self.log.debug("using latest lede imagebuilder")
            self.imagebuilder_release = get_latest_release("lede")
        self.log.debug("using imagebuilder %s", self.imagebuilder_release)
        self.target = target
        self.subtarget = subtarget
        self.root = os.path.dirname(os.path.realpath(__file__))
        self.workdir = get_dir("workdir")

        self.path = os.path.join(self.workdir, self.distro, self.version, self.target, self.subtarget)
        self.log.debug("imagebuilder path %s", self.path)

    def created(self):
        if os.path.exists(os.path.join(self.path, "Makefile")):
            return True

    def parse_packages_arch(self):
        logging.debug("parse_packages_arch")
        with open(os.path.join(self.path, ".config"), "r") as config:
            for line in config:
                if line.startswith("CONFIG_TARGET_ARCH_PACKAGES"):
                    return re.match(r'.*"(.+)"', line).group(1)

    def patch_makefile(self):
        self.log.debug("patch makefile")
        cmdline = ["patch", "-p4", "--dry-run", "-i", get_root() + "/imagebuilder-add-package_list-function.patch"]
        proc = subprocess.Popen(
            cmdline,
            cwd=self.path,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )

        output, erros = proc.communicate()
        return_code = proc.returncode

        if return_code == 0:
            self.log.debug("apply makefile patch")
            cmdline.pop(2)
            proc = subprocess.Popen(
                cmdline,
                cwd=self.path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT
            )
        else:
            if not output.decode('utf-8').startswith("checking file Makefile\nReversed"):
                self.log.error("could not path imagebuilder makefile")
                self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, "patch_fail")

    def add_custom_repositories(self):
        self.pkg_arch = self.parse_packages_arch()
        self.log.info("adding custom repositories")
        custom_repositories = None
        custom_repositories_path = os.path.join(self.root, "distributions", self.distro, "repositories.conf")
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
        if self.imagebuilder_release == "snapshots":
            custom_repositories = re.sub(r"/releases/snapshots", "/snapshots", custom_repositories)
        return custom_repositories

    def download_url(self):
        if self.imagebuilder_release == "snapshots":
            imagebuilder_download_url = os.path.join(self.config.get("imagebuilder_snapshots_url"), "targets", self.target, self.subtarget)
        else:
            imagebuilder_download_url = os.path.join(self.config.get("imagebuilder_url"), self.imagebuilder_release, "targets", self.target, self.subtarget)
        self.log.debug(imagebuilder_download_url)
        return imagebuilder_download_url

    def tar_name(self, remove_subtarget=False):
        name_array = ["lede-imagebuilder"]
        if not self.imagebuilder_release is "snapshots":
            name_array.append(self.imagebuilder_release)
        name_array.append(self.target)
        # some imagebuilders have -generic removed
        if not remove_subtarget:
            name_array.append(self.subtarget)
        name = "-".join(name_array)
        name += ".Linux-x86_64.tar.xz"
        return name

    def run(self):
        self.log.info("downloading imagebuilder %s", self.path)
        if not self.created():
            create_folder(self.path)

            regular_tar_url = os.path.join(self.download_url(), self.tar_name())
            if get_statuscode(regular_tar_url) != 404:
                if not self.download(regular_tar_url):
                    return False
            else:
                # this is only due to arm64 missing -generic in filename
                # this is very ugly, can this just be deleted?
                special_tar_url = os.path.join(self.download_url(), self.tar_name(True))
                if get_statuscode(special_tar_url) != 404:
                    self.log.debug("remove -generic from url")

                    if not self.download(special_tar_url):
                        return False
                else:
                    self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'download_fail')
                    return False
        self.patch_makefile()
        self.add_custom_repositories()
        self.pkg_arch = self.parse_packages_arch()
        self.parse_info()
        self.parse_packages()
        self.log.info("initialized imagebuilder %s", self.path)
        self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'ready')
        return True

    def download(self, url):
        with tempfile.TemporaryDirectory(dir=get_dir("tempdir")) as tempdir:
            self.log.info("downloading signature")
            urllib.request.urlretrieve(os.path.join(self.download_url(), "sha256sums"), (tempdir + "/sha256sums"))
            urllib.request.urlretrieve(os.path.join(self.download_url(), "sha256sums.gpg"), (tempdir + "/sha256sums.gpg"))
            if not check_signature(tempdir):
                self.log.warn("bad signature")
                self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'signature_fail')
                return False
            self.log.debug("good signature")
            tar_name = url.split("/")[-1]
            tar_path = os.path.join(tempdir, tar_name)
            self.log.info("downloading url %s", url)
            urllib.request.urlretrieve(url, tar_path)

            cmdline = ["sha256sum", "-c", "--ignore-missing", "sha256sums"]
            proc = subprocess.Popen(
                cmdline,
                cwd=tempdir,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT
            )

            sha256_output, erros = proc.communicate()
            return_code = proc.returncode
            sha256_output = sha256_output.decode('utf-8')
            if not sha256_output == "{}: OK\n".format(tar_name):
                self.log.warn("bad sha256sum")
                self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'sha256sum_fail')
                return False
            self.log.debug("good sha256sum")

            os.system("tar -C {} --strip=1 -xf {}".format(self.path, tar_path))
            return True
        return False

    def as_array(self):
        return [self.distro, self.release, self.target, self.subtarget]

    def parse_info(self):
        self.log.debug("parse info")
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
            self.database.insert_profiles(self.distro, self.release, self.target, self.subtarget, default_packages, profiles)
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
        if returnCode == 0:
            packages = re.findall(r"(.+?) - (.+?) - .*\n", output)
            self.log.info("found {} packages for {} {} {} {}".format(len(packages), self.distro, self.release, self.target, self.subtarget))
            self.database.insert_packages_available(self.distro, self.release, self.target, self.subtarget, packages)
        else:
            print(output)
            self.log.warning("could not receive packages of %s/%s", self.target, self.subtarget)
