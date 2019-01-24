import threading
import glob
import paramiko
import re
from queue import Queue
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
        if self.location.startswith("/") or self.location.startswith("."):
            self.local = True
        else:
            self.local = False
            self.sftp_setup()
        self.queue = queue
        self.job = job
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")
        self.params = {}

    def setup_meta(self):
        self.log.debug("setup meta")
        cmdline = "git clone https://github.com/aparcar/meta-imagebuilder.git .".split(" ")
        if self.local:
            os.makedirs(self.location, exist_ok=True)
            if not os.path.exists(self.location + "/meta"):
                return_code, stdout, stderr = self.run_cmd(cmdline)
        else:
            if not self.rexists("meta"):
                return_code, stdout, stderr = self.run_cmd(cmdline)

        if return_code != 0:
            self.log.error("failed to setup meta ImageBuilder:\n%s", stderr)
            exit()
        else:
            self.log.info("meta ImageBuilder successfully setup")

    def write_log(self, path, stdout=None, stderr=None):
        with open(path, "a") as log_file:
            log_file.write("### BUILD COMMAND:\n\n")
            for key, value in self.params.items():
                log_file.write("{}={}\n".format(key.upper(), str(value)))
            log_file.write("sh meta\n")
            if stdout:
                log_file.write("\n\n### STDOUT:\n\n" + stdout)
            if stderr:
                log_file.write("\n\n### STDERR:\n\n" + stderr)

    # build image
    def build(self):
        self.log.debug("create and parse manifest")

        # fail path in case of erros
        fail_log_path = self.config.get_folder("download_folder") + "/faillogs/faillog-{}.txt".format(self.params["request_hash"])

        self.image = Image(self.params)

        # first determine the resulting manifest hash
        return_code, manifest_content, errors = self.run_cmd("manifest")

        if return_code == 0:
            self.image.params["manifest_hash"] = get_hash(manifest_content, 15)

            manifest_pattern = r"(.+) - (.+)\n"
            manifest_packages = dict(re.findall(manifest_pattern, manifest_content))
            self.database.add_manifest_packages(self.image.params["manifest_hash"], manifest_packages)
            self.log.info("successfully parsed manifest")
        else:
            self.log.error("couldn't determine manifest")
            self.write_log(fail_log_path, stderr=errors)
            self.database.set_image_requests_status(self.params["request_hash"], "manifest_fail")
            return False

        # set directory where image is stored on server
        self.image.set_image_dir()
        self.log.debug("dir %s", self.image.params["dir"])

        # calculate hash based on resulted manifest
        self.image.params["image_hash"] = get_hash(" ".join(self.image.as_array("manifest_hash")), 15)

        # set log path in case of success
        success_log_path = self.image.params["dir"] + "/buildlog-{}.txt".format(self.params["image_hash"])

        # set build_status ahead, if stuff goes wrong it will be changed
        self.build_status = "created"

        # check if image already exists
        if not self.image.created():
            self.log.info("build image")

            self.build_dir = "/tmp/" + self.params["request_hash"]
            os.makedirs(self.build_dir)

            # now actually build the image with manifest hash as EXTRA_IMAGE_NAME
            self.params["worker"] = self.location
            self.params["BIN_DIR"] = self.build_dir
            self.params["j"] = str(os.cpu_count())
            self.params["EXTRA_IMAGE_NAME"] = self.params["manifest_hash"]
            # if uci defaults are added, at least at parts of the hash to time image name
            if self.params["defaults_hash"]:
                self.defaults_to_file()

                # tell ImageBuilder to integrate files
                self.params["FILES"] = self.build_dir + "/files/"
                self.params["EXTRA_IMAGE_NAME"] += "-" + self.params["defaults_hash"][:6]

            # download is already performed for manifest creation
            self.params["NO_DOWNLOAD"] = "1"

            build_start = time.time()
            return_code, buildlog, errors = self.run_cmd("image")
            self.image.params["build_seconds"] = int(time.time() - build_start)

            if return_code == 0:
                # create folder in advance

                if not self.local:
                    self.copy_from_remote()

                os.makedirs(self.image.params["dir"], exist_ok=True)

                self.log.debug(os.listdir(self.build_dir))

                for filename in os.listdir(self.build_dir):
                    if os.path.exists(self.image.params["dir"] + "/" + filename):
                        break
                    shutil.move(self.build_dir + "/" + filename, self.image.params["dir"])

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
                        self.database.set_image_requests_status(self.params["request_hash"], "imagesize_fail")
                        self.write_log(fail_log_path, buildlog, errors)
                        return False
                    else:
                        self.build_status = "no_sysupgrade"
                        self.image.params["sysupgrade"] = ""
                else:
                    self.image.params["sysupgrade"] = os.path.basename(sysupgrade[0])

                self.write_log(success_log_path, buildlog)
                self.database.add_image(self.image.get_params())
                self.log.info("build successfull")
            else:
                self.log.info("build failed")
                self.database.set_image_requests_status(self.params["request_hash"], 'build_fail')
                self.write_log(fail_log_path, buildlog, errors)
                return False

        self.log.info("link request %s to image %s", self.params["request_hash"], self.params["image_hash"])
        self.database.done_build_job(self.params["request_hash"], self.image.params["image_hash"], self.build_status)
        return True

    def run(self):
        self.setup_meta()

        while True:
            self.params = self.queue.get()
            self.params.pop("id")
            self.params.pop("image_hash")
            self.version_config = self.config.version(
                    self.params["distro"], self.params["version"])
            if self.job == "image":
                self.build()
            elif self.job == "update":
                self.info()
                self.parse_packages()

    def info(self):
        self.parse_info()
        if os.path.exists(os.path.join(
                self.location, "imagebuilder",
                self.params["distro"], self.params["version"],
                self.params["target"], self.params["subtarget"],
                "target/linux", self.params["target"],
                "base-files/lib/upgrade/platform.sh")):
            self.log.info("%s target is supported", self.params["target"])
            self.database.insert_supported(self.params)

    def run_cmd(self, cmd, meta=True):
        if meta:
            cmd = ["sh", "meta", cmd]
        if self.local:
            return_code, stdout, stderr = self.run_local(cmd)
            output = stdout.decode('utf-8')
            errors = stderr.decode('utf-8')
        else:
            return_code, stdout, stderr = self.run_remote(cmd)
            output = stdout.read()
            errors = stderr.read()

        return (return_code, output, errors)

    def defaults_to_file(self):
        defaults_dir = self.build_dir + "/files/etc/uci-defaults/"
        # request defaults content from database
        defaults_content = self.database.get_defaults(self.params["defaults_hash"])
        # create folder to store uci defaults
        if self.local:
            os.makedirs(defaults_dir)
            with open(defaults_dir + "99-server-defaults", "w") as defaults_file:
                defaults_file.write(defaults_content) # TODO check if special encoding is required
        else:
            self.sftp.mkdir(defaults_dir)
            with self.sftp.open(defaults_dir + "99-server-defaults", "w") as defaults_file:
                defaults_file.write(defaults_content) # TODO check if special encoding is required

    def sftp_setup(self):
        username, hostname, port = self.ssh_login_data()
        t = paramiko.Transport((hostname, port))
        pk = paramiko.RSAKey.from_private_key(open('~/.ssh/id_rsa')) # TODO is that a clean solution?
        t.connect(username=username, pkey=pk)
        self.sftp = paramiko.SFTPClient.from_transport(t)

    def copy_from_remote(self):
        username, hostname, port = self.ssh_login_data()
        for remote_file in self.sftp.listdir(self.build_dir):
            self.sftp.get(self.build_dir + "/" + remote_file ,
                    self.image.params["dir"])

    def rexists(self, path):
        try:
            self.sftp.stat(path)
        except IOError as e:
            return False
        else:
            return True

    # parses worker address, username and port
    def ssh_login_data(self):
        port = 22
        username = "root"
        hostname = self.location
        if "@" in hostname:
            username, hostname = hostname.split("@")

        if ":" in hostname:
            hostname, port = hostname.split(":")

        return (username, hostname, int(port))

    def run_remote(self, cmdline):
        username, hostname, port = self.ssh_login_data()
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, port=port, username=username, key_filename="~/.ssh/id_rsa") # TODO ?!

        stdin, stdout, stderr = client.exec_command(" ".join(cmdline), environment=self.params)

        client.close()

        return (0, stdout, stderr)

    def run_local(self, cmdline):
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
            stderr=subprocess.PIPE,
            shell=False,
            env=env
        )

        stdout, stderr = proc.communicate()
        return_code = proc.returncode

        return (return_code, stdout, stderr)

    def parse_info(self):
        self.log.debug("parse info")

        return_code, output, errors = self.run_cmd("info")

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

        return_code, output, errors = self.run_cmd("package_list")

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
