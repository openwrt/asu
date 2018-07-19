import logging

from utils.common import get_hash
from utils.config import Config
from utils.database import Database

class Image():
    def __init__(self, params):
        self.config = Config()
        self.log = logging.getLogger(__name__)
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")
        self.params = params

        # sort and deduplicate requested packages
        if "packages" in self.params:
            self.params["packages"] = " ".join(sorted(list(set(self.params["packages"].split(" ")))))
        else:
            self.params["packages"] = ""

        # create hash of requested packages and store in database
        self.params["package_hash"] = get_hash(self.params["packages"], 12)
        self.database.insert_hash(self.params["package_hash"], self.params["packages"])

    # write buildlog.txt to image dir
    def store_log(self, buildlog):
        self.log.debug("write log")
        with open(self.params["dir"] + "/buildlog.txt", "a") as buildlog_file:
            buildlog_file.writelines(buildlog)

    # return dir where image is stored on server
    def set_image_dir(self):
        self.params["dir"] = "/".join([
            self.config.get_folder("download_folder"),
            self.params["distro"],
            self.params["release"],
            self.params["target"],
            self.params["subtarget"],
            self.params["profile"],
            self.params["manifest_hash"]
            ])

    # return params of array in specific order
    def as_array(self, extra=None):
        as_array = [
            self.params["distro"],
            self.params["release"],
            self.params["target"],
            self.params["subtarget"],
            self.params["profile"]
            ]
        if extra:
            as_array.append(self.params[extra])
        return as_array

    def get_params(self):
        return {
            "distro": self.params["distro"],
            "release": self.params["release"],
            "target": self.params["target"],
            "subtarget": self.params["subtarget"],
            "profile": self.params["profile"],
            "image_hash": self.params["image_hash"],
            "manifest_hash": self.params["manifest_hash"],
            "worker": self.params["worker"],
            "sysupgrade": self.params["sysupgrade"]
        }
