import logging
import tarfile
import glob
import re
import shutil
import urllib.request
import tempfile
import logging
import os
import os.path
import threading
import subprocess

from utils.common import get_statuscode, check_signature
from utils.config import Config

class ImageBuilder(threading.Thread):
    def __init__(self, distro, version, target, subtarget):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.distro = distro
        self.version = version
        self.release = version
        if self.release != 'snapshot':
            self.imagebuilder_distro = self.config.get(self.distro).get("parent_distro", self.distro)
            self.imagebuilder_release = self.config.get(self.distro).get("parent_release", self.release)
        else:
            self.imagebuilder_distro = "openwrt"
            self.imagebuilder_release = "snapshot"
        self.log.debug("using imagebuilder %s", self.imagebuilder_release)
        self.target = target
        self.subtarget = subtarget
        self.path = os.path.join(self.config.get_folder("imagebuilder_folder"), self.distro, self.version, self.target, self.subtarget)
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
        patches = glob.glob(os.path.join(os.getcwd(), "worker/*.patch"))

        for patch in patches:
            cmdline = ["patch", "-p4", "--dry-run", "-i", os.path.join(os.getcwd(), "worker", patch)]
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
                self.log.info("patch makefile with %s", patch)
                cmdline.pop(2)
                proc = subprocess.Popen(
                    cmdline,
                    cwd=self.path,
                    stdout=subprocess.PIPE,
                    shell=False,
                    stderr=subprocess.STDOUT
                )
                output, erros = proc.communicate()
            else:
                if not output.decode('utf-8').startswith("checking file Makefile\nReversed"):
                    self.log.error("could not patch imagebuilder makefile with %s", patch)

    def add_custom_repositories(self):
        self.pkg_arch = self.parse_packages_arch()
        self.log.info("check custom repositories of release")
        custom_repositories = self.config.release(self.distro, self.release).get("repositories")
        if not custom_repositories:
            self.log.info("check custom repositories of distro")
            custom_repositories = self.config.get(self.distro).get("repositories")
        if custom_repositories:
            self.log.info("add custom repositories")
            with open(os.path.join(self.path, "repositories.conf"), "w") as repositories:
                repositories.write(self.fill_repositories_template(custom_repositories))
        else:
            self.log.info("no custom repositories of distro")

    def fill_repositories_template(self, custom_repositories):
        custom_repositories = re.sub(r"{{ distro }}", self.distro, custom_repositories)
        custom_repositories = re.sub(r"{{ imagebuilder_release }}", self.imagebuilder_release, custom_repositories)
        custom_repositories = re.sub(r"{{ release }}", self.release, custom_repositories)
        custom_repositories = re.sub(r"{{ target }}", self.target, custom_repositories)
        custom_repositories = re.sub(r"{{ subtarget }}", self.subtarget, custom_repositories)
        custom_repositories = re.sub(r"{{ pkg_arch }}", self.pkg_arch, custom_repositories)
        return custom_repositories

    def download_url(self):
        print(self.imagebuilder_release)
        if self.imagebuilder_release == "snapshot":
            imagebuilder_download_url = os.path.join(self.config.get(self.imagebuilder_distro).get("snapshots_url"), "targets", self.target, self.subtarget)
        else:
            imagebuilder_download_url = os.path.join(self.config.get(self.imagebuilder_distro).get("releases_url"), self.imagebuilder_release, "targets", self.target, self.subtarget)
        self.log.debug(imagebuilder_download_url)
        return imagebuilder_download_url

    def tar_name(self, remove_subtarget=False):
        name_array = [self.imagebuilder_distro, "imagebuilder"]
        if not self.imagebuilder_release is "snapshot":
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
            os.makedirs(self.path, exist_ok=True)

            regular_tar_url = os.path.join(self.download_url(), self.tar_name())
            if get_statuscode(regular_tar_url) != 404:
                if not self.download(regular_tar_url):
                    return False
            else:
                self.log.info("did not find regular imagebuilder name")
                # this is only due to arm64 missing -generic in filename
                # this is very ugly, can this just be deleted?
                special_tar_url = os.path.join(self.download_url(), self.tar_name(True))
                if get_statuscode(special_tar_url) != 404:
                    self.log.debug("remove -generic from url")

                    if not self.download(special_tar_url):
                        return False
                else:
                    return False
            self.patch_makefile()
            self.add_custom_repositories()
            self.pkg_arch = self.parse_packages_arch()

        self.log.info("initialized imagebuilder %s", self.path)
        return True

    def download(self, url):
        with tempfile.TemporaryDirectory(dir=self.config.get_folder("tempdir")) as tempdir:
            self.log.info("downloading signature")
            urllib.request.urlretrieve(os.path.join(self.download_url(), "sha256sums"), (tempdir + "/sha256sums"))
            urllib.request.urlretrieve(os.path.join(self.download_url(), "sha256sums.gpg"), (tempdir + "/sha256sums.gpg"))
            if not check_signature(tempdir) and not self.release == 'snapshot':
                self.log.warn("bad signature")
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
            if not sha256_output == "{}: OK\n".format(tar_name) and not self.release == 'snapshot':
                self.log.warn("bad sha256sum")
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
            return(default_packages, profiles)
        else:
            logging.error("could not receive profiles of %s/%s", self.target, self.subtarget)
            return False

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
            return(packages)
        else:
            print(output)
            self.log.warning("could not receive packages of %s/%s", self.target, self.subtarget)
