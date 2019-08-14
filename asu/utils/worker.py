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

from asu.utils.image import Image
from asu.utils.common import get_hash
from asu.utils.config import Config
from asu.utils.database import Database


class Worker(threading.Thread):
    def __init__(self, location, job, queue):
        self.location = location
        self.queue = queue
        self.job = job
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")

    def setup_meta(self):
        self.log.debug("setup meta")
        os.makedirs(self.location, exist_ok=True)
        if not os.path.exists(self.location + "/meta"):
            self.log.info("Initial clone")
            cmdline = "git clone https://github.com/aparcar/meta-imagebuilder.git ."
        else:
            self.log.info("Update pull")
            cmdline = "git pull"

        proc = subprocess.Popen(
            cmdline.split(),
            cwd=self.location,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        output, errors = proc.communicate()
        return_code = proc.returncode
        output = output.decode("utf-8")
        errors = errors.decode("utf-8")
        self.log.debug(output)

        if return_code != 0:
            self.log.error("failed to setup/update meta ImageBuilder")
            self.log.warning(errors)
            exit(1)

        self.log.info("meta ImageBuilder successfully setup")

    def write_log(self, path, stdout=None, stderr=None):
        with open(path, "a") as log_file:
            log_file.write("### BUILD COMMAND:\n\n")
            for key, value in self.params.items():
                log_file.write('export {}="{}"\n'.format(key.upper(), str(value)))
            log_file.write("./meta image\n")
            if stdout:
                log_file.write("\n\n### STDOUT:\n\n" + stdout)
            if stderr:
                log_file.write("\n\n### STDERR:\n\n" + stderr)

    # build image
    def build(self):
        self.log.debug("create and parse manifest")

        # fail path in case of erros
        fail_log_path = self.config.get_folder(
            "download_folder"
        ) + "/faillogs/faillog-{}.txt".format(self.params["request_hash"])

        self.image = Image(self.params)

        if self.params["packages_hash"]:
            packages_image = set(self.database.get_packages_image(self.params))
            self.log.debug("packages_image %s", packages_image)
            packages_requested = set(
                self.database.get_packages_hash(self.params["packages_hash"])
            )
            self.log.debug("packages_requested %s", packages_requested)
            packages_remove = packages_image - packages_requested
            self.log.debug("packages_remove %s", packages_remove)
            packages_requested.update(set(map(lambda x: "-" + x, packages_remove)))
            self.params["packages"] = " ".join(packages_requested)
            self.log.debug("packages param %s", self.params["packages"])
        else:
            self.log.debug("build package with default packages")

        # first determine the resulting manifest hash
        return_code, manifest_content, errors = self.run_meta("manifest")

        if return_code == 0:
            self.image.params["manifest_hash"] = get_hash(manifest_content, 15)

            manifest_pattern = r"(.+) - (.+)\n"
            manifest_packages = re.findall(manifest_pattern, manifest_content)
            self.database.add_manifest_packages(
                self.image.params["manifest_hash"], manifest_packages
            )
            self.log.info("successfully parsed manifest")
        else:
            self.log.error("couldn't determine manifest")
            self.log.debug(manifest_content)
            self.log.debug(errors)
            self.write_log(fail_log_path, stderr=errors)
            self.database.set_requests_status(
                self.params["request_hash"], "manifest_fail"
            )
            return False

        # set directory where image is stored on server
        self.image.set_image_dir()
        self.log.debug("dir %s", self.image.params["dir"])

        # calculate hash based on resulted manifest
        self.image.params["image_hash"] = get_hash(
            " ".join(self.image.as_array("manifest_hash")), 15
        )

        # set build_status ahead, if stuff goes wrong it will be changed
        self.build_status = "created"

        # check if image already exists
        if not self.image.created() or not self.database.image_exists(
            self.params["image_hash"]
        ):
            self.log.info("build image")
            with tempfile.TemporaryDirectory() as build_dir:
                # now actually build the image with manifest hash as
                # EXTRA_IMAGE_NAME
                self.log.info("build image at %s", build_dir)
                self.params["worker"] = self.location
                self.params["BIN_DIR"] = build_dir
                self.params["j"] = str(os.cpu_count())
                self.params["EXTRA_IMAGE_NAME"] = self.params["manifest_hash"]
                # if uci defaults are added, at least at parts of the hash to
                # time image name
                if self.params["defaults_hash"]:
                    defaults_dir = build_dir + "/files/etc/uci-defaults/"
                    # create folder to store uci defaults
                    os.makedirs(defaults_dir)
                    # request defaults content from database
                    defaults_content = self.database.get_defaults(
                        self.params["defaults_hash"]
                    )
                    # TODO check if special encoding is required
                    with open(
                        defaults_dir + "99-server-defaults", "w"
                    ) as defaults_file:
                        defaults_file.write(defaults_content)

                    # tell ImageBuilder to integrate files
                    self.params["FILES"] = build_dir + "/files/"
                    self.params["EXTRA_IMAGE_NAME"] += (
                        "-" + self.params["defaults_hash"][:6]
                    )

                # download is already performed for manifest creation
                self.params["NO_DOWNLOAD"] = "1"

                build_start = time.time()
                return_code, buildlog, errors = self.run_meta("image")
                self.image.params["build_seconds"] = int(time.time() - build_start)

                if return_code == 0:
                    # create folder in advance
                    os.makedirs(self.image.params["dir"], exist_ok=True)

                    self.log.debug(os.listdir(build_dir))

                    for filename in os.listdir(build_dir):
                        if os.path.exists(self.image.params["dir"] + "/" + filename):
                            break
                        shutil.move(
                            build_dir + "/" + filename, self.image.params["dir"]
                        )

                    if buildlog.find("too big") != -1:
                        self.log.warning("created image was to big")
                        self.database.set_requests_status(
                            self.params["request_hash"], "imagesize_fail"
                        )
                        self.write_log(fail_log_path, buildlog, errors)
                        return False

                    self.database.insert_dict("images", self.image.get_params())
                    success_log_path = (
                        os.path.join(
                            self.config.get_folder("download_folder"),
                            *self.database.get_image_path(
                                self.params["image_hash"]
                            ).values()
                        )
                        + ".log"
                    )
                    self.write_log(success_log_path, buildlog)
                    self.log.info("build successfull")
                else:
                    self.log.info("build failed")
                    self.database.set_requests_status(
                        self.params["request_hash"], "build_fail"
                    )
                    self.write_log(fail_log_path, buildlog, errors)
                    return False
        else:
            self.log.info("image already there")

        self.log.info(
            "link request %s to image %s",
            self.params["request_hash"],
            self.params["image_hash"],
        )
        self.database.done_build_job(
            self.params["request_hash"],
            self.image.params["image_hash"],
            self.build_status,
        )
        return True

    def run(self):
        self.setup_meta()

        while True:
            self.params = self.queue.get()
            self.version_config = self.config.version(
                self.params["distro"], self.params["version"]
            )
            if self.job == "image":
                self.build()
            elif self.job == "update":
                self.parse_packages()
                self.info()

    def info(self):
        self.log.debug("parse info")

        return_code, output, errors = self.run_meta("info")

        if return_code == 0:
            revision_pattern = r'.*\nCurrent Revision: "(.*)"\n'
            revision_match = re.match(revision_pattern, output, re.M)
            if revision_match:
                revision = revision_match.group(1)
            else:
                revision = ""

            self.database.insert_revision(
                self.params["distro"],
                self.params["version"],
                self.params["target"],
                revision,
            )

            default_packages_pattern = r"(?:.*\n)*Default Packages: (.+)\n"
            default_packages = (
                re.match(default_packages_pattern, output, re.M).group(1).split()
            )
            self.log.debug("default packages: %s", default_packages)

            profiles = re.findall(
                "(.+):\n    (.+)"
                "\n    Packages: (.*)"
                "\n(?:    hasImageMetadata: )?(\d)?"
                "(?:(?:\n    SupportedDevices: )(.*?)(?:\n))?",
                output,
            )
            self.log.debug(profiles)
            if not profiles:
                profiles = []
            self.database.insert_profiles(
                self.params["distro"],
                self.params["version"],
                self.params["target"],
                default_packages,
                profiles,
            )
        else:
            self.log.error("could not receive profiles")
            self.log.debug(output)
            self.log.debug(errors)
            return False

    def run_meta(self, cmd):
        cmdline = ["sh", "meta", cmd]
        env = os.environ.copy()

        if "parent_version" in self.version_config:
            self.params["IB_VERSION"] = self.version_config["parent_version"]
        if "repos" in self.version_config:
            self.params["REPOS"] = self.version_config["repos"]

        for key, value in self.params.items():
            env[key.upper()] = str(value)  # TODO convert meta script to Makefile

        proc = subprocess.Popen(
            cmdline,
            cwd=self.location,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        output, errors = proc.communicate()
        return_code = proc.returncode
        output = output.decode("utf-8")
        errors = errors.decode("utf-8")

        return (return_code, output, errors)

    def parse_packages(self):
        self.log.info("receive packages")

        return_code, output, errors = self.run_meta("package_list")

        if return_code == 0:
            packages = re.findall(r"(.+?) - (.+?) - .*\n", output)
            self.log.info("found {} packages".format(len(packages)))
            self.database.insert_packages_available(
                self.params["distro"],
                self.params["version"],
                self.params["target"],
                packages,
            )
        else:
            self.log.warning("could not receive packages")
            self.log.debug(output)
            self.log.debug(errors)
