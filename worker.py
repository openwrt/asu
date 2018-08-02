import threading
import glob
import re
import shutil
import tempfile
import os
import os.path
import subprocess
import logging
import time

from utils.image import Image
from utils.common import get_hash
from utils.config import Config
from utils.database import Database

class Worker(threading.Thread):
    def __init__(self, location, job, params):
        self.location = location
        self.job = job
        self.params = params
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")
        self.version_config = self.config.version(
                self.params["distro"], self.params["version"])

    def setup_meta(self):
        os.makedirs(self.location, exist_ok=True)
        self.log.debug("setup meta")
        cmdline = "git clone https://github.com/aparcar/meta-imagebuilder.git ."
        proc = subprocess.Popen(
            cmdline.split(" "),
            cwd=self.location,
            stdout=subprocess.PIPE,
            shell=False,
        )

        _, errors = proc.communicate()
        return_code = proc.returncode

        return return_code

    def setup(self):
        self.log.debug("setup")
        return_code, output, errors = self.run_meta("download")
        if return_code == 0:
            self.log.info("setup complete")
        else:
            self.log.error("failed to download imagebuilder")
            print(output)
            print(errors)
            exit()

    # write buildlog.txt to image dir
    def store_log(self, buildlog):
        self.log.debug("write log")
        with open(self.image.params["dir"] + "/buildlog-{}.txt".format(self.params["image_hash"]), "a") as buildlog_file:
            buildlog_file.writelines(buildlog)

    # build image
    def build(self):
        self.log.debug("create and parse manifest")
        self.image = Image(self.params)

        # first determine the resulting manifest hash
        return_code, manifest_content, errors = self.run_meta("manifest")

        self.log.debug(manifest_content)

        if return_code == 0:
            self.image.params["manifest_hash"] = get_hash(manifest_content, 15)

            manifest_pattern = r"(.+) - (.+)\n"
            manifest_packages = dict(re.findall(manifest_pattern, manifest_content))
            self.database.add_manifest_packages(self.image.params["manifest_hash"], manifest_packages)
            self.log.info("successfully parsed manifest")
        else:
            print(errors)
            print(manifest_content)
            self.log.error("couldn't determine manifest")
            self.database.set_image_requests_status(self.params["request_hash"], "manifest_fail")
            return False

        # set directory where image is stored on server
        self.image.set_image_dir()
        self.log.debug("dir %s", self.image.params["dir"])

        # calculate hash based on resulted manifest
        self.image.params["image_hash"] = get_hash(" ".join(self.image.as_array("manifest_hash")), 15)

        # set build_status ahead, if stuff goes wrong it will be changed
        self.build_status = "created"

        # check if image already exists
        if not self.image.created():
            self.log.info("build image")
            with tempfile.TemporaryDirectory(dir=self.config.get_folder("tempdir")) as build_dir:
                # now actually build the image with manifest hash as EXTRA_IMAGE_NAME
                self.params["worker"] = self.location
                self.params["BIN_DIR"] = build_dir
                self.params["j"] = str(os.cpu_count())
                self.params["EXTRA_IMAGE_NAME"] = self.params["manifest_hash"]

                return_code, buildlog, errors = self.run_meta("image")

                if return_code == 0:

                    # create folder in advance
                    os.makedirs(self.image.params["dir"], exist_ok=True)

                    self.log.debug(os.listdir(build_dir))

                    for filename in os.listdir(build_dir):
                        if os.path.exists(self.image.params["dir"] + "/" + filename):
                            break
                        shutil.move(build_dir + "/" + filename, self.image.params["dir"])

                    # possible sysupgrade names, ordered by likeliness
                    possible_sysupgrade_files = [ "*-squashfs-sysupgrade.bin",
                            "*-squashfs-sysupgrade.tar", "*-squashfs.trx",
                            "*-squashfs.chk", "*-squashfs.bin",
                            "*-squashfs-sdcard.img.gz", "*-combined-squashfs*",
                            "*.img.gz"]

                    sysupgrade = None

                    for sysupgrade_file in possible_sysupgrade_files:
                        sysupgrade = glob.glob(self.image.params["dir"] + "/" + sysupgrade_file)
                        if sysupgrade:
                            break

                    if not sysupgrade:
                        self.log.debug("sysupgrade not found")
                        if buildlog.find("too big") != -1:
                            self.log.warning("created image was to big")
                            self.store_log(buildlog)
                            self.database.set_image_requests_status(self.params["request_hash"], "imagesize_fail")
                            return False
                        else:
                            self.build_status = "no_sysupgrade"
                            self.image.params["sysupgrade"] = ""
                    else:
                        self.image.params["sysupgrade"] = os.path.basename(sysupgrade[0])
                        self.store_log(buildlog)

                    self.database.add_image(self.image.get_params())
                    self.log.info("build successfull")
                else:
                    print(buildlog)
                    self.log.info("build failed")
                    self.database.set_image_requests_status(self.params["request_hash"], 'build_fail')
     #               self.store_log(buildlog)
                    return False

        self.log.info("link request %s to image %s", self.params["request_hash"], self.params["image_hash"])
        self.database.done_build_job(self.params["request_hash"], self.image.params["image_hash"], self.build_status)
        return True

    def run(self):
        if not os.path.exists(self.location + "/meta"):
            if self.setup_meta():
                self.log.error("failed to setup meta ImageBuilder")
                exit()
        self.setup()
        if self.job == "image":
            self.build()
        elif self.job == "info":
            self.parse_info()
            if os.path.exists(os.path.join(
                    self.location, "imagebuilder",
                    self.params["distro"], self.params["version"],
                    self.params["target"], self.params["subtarget"],
                    "target/linux", self.params["target"],
                    "base-files/lib/upgrade/platform.sh")):
                self.log.info("%s target is supported", self.params["target"])
                self.database.insert_supported(self.params)
        elif self.job == "package_list":
            self.parse_packages()
            self.database.subtarget_synced(self.params)

    def run_meta(self, cmd):
        cmdline = ["sh", "meta", cmd ]
        env = os.environ.copy()

        if "parent_version" in self.version_config:
            self.params["IB_VERSION"] = self.version_config["parent_version"]
        if "repos" in self.version_config:
            self.params["REPOS"] = self.version_config["repos"]

        for key, value in self.params.items():
            env[key.upper()] = str(value) # TODO convert meta script to Makefile


        proc = subprocess.Popen(
            cmdline,
            cwd=self.location,
            stdout=subprocess.PIPE,
            shell=False,
            env=env
        )

        output, errors = proc.communicate()
        return_code = proc.returncode
        output = output.decode('utf-8')

        return (return_code, output, errors)


    def parse_info(self):
        self.log.debug("parse info")

        return_code, output, errors = self.run_meta("info")

        if return_code == 0:
            default_packages_pattern = r"(.*\n)*Default Packages: (.+)\n"
            default_packages = re.match(default_packages_pattern, output, re.M).group(2)
            logging.debug("default packages: %s", default_packages)

            profiles_pattern = r"(.+):\n    (.+)\n    Packages: (.*)\n"
            profiles = re.findall(profiles_pattern, output)
            if not profiles:
                profiles = []
            self.database.insert_profiles({
                "distro": self.params["distro"],
                "version": self.params["version"],
                "target": self.params["target"],
                "subtarget": self.params["subtarget"]},
                default_packages, profiles)
        else:
            logging.error("could not receive profiles")
            return False

    def parse_packages(self):
        self.log.info("receive packages")

        return_code, output, errors = self.run_meta("package_list")

        if return_code == 0:
            packages = re.findall(r"(.+?) - (.+?) - .*\n", output)
            self.log.info("found {} packages".format(len(packages)))
            self.database.insert_packages_available({
                "distro": self.params["distro"],
                "version": self.params["version"],
                "target": self.params["target"],
                "subtarget": self.params["subtarget"]}, packages)
        else:
            self.log.warning("could not receive packages")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)
    config = Config()
    database = Database(config)
    location = config.get("worker")[0]
    while True:
        image = database.get_build_job()
        if image:
            print(image)
            worker = Worker(location, "image", image)
            worker.run() # TODO no threading just yet
        outdated_subtarget = database.get_subtarget_outdated()
        if outdated_subtarget:
            print(outdated_subtarget)
            log.info("found outdated subtarget %s", outdated_subtarget)
            worker = Worker(location, "info", outdated_subtarget)
            worker.run()
            worker = Worker(location, "package_list", outdated_subtarget)
            worker.run()
        time.sleep(5)

    # TODO reimplement
    #def diff_packages(self):
    #    profile_packages = self.vanilla_packages
    #    for package in self.packages:
    #        if package in profile_packages:
    #            profile_packages.remove(package)
    #    for remove_package in profile_packages:
    #        self.packages.append("-" + remove_package)

