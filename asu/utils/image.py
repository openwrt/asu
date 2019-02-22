import logging
import os.path

from asu.utils.common import get_hash
from asu.utils.config import Config
from asu.utils.database import Database


class Image:
    def __init__(self, params):
        self.config = Config()
        self.log = logging.getLogger(__name__)
        self.log.info("config initialized")
        self.database = Database(self.config)
        self.log.info("database initialized")
        self.params = params

        if not "defaults_hash" in self.params:
            self.params["defaults_hash"] = ""
            if "defaults" in self.params:
                if self.params["defaults"] != "":
                    self.params["defaults_hash"] = get_hash(self.params["defaults"], 32)
        if not self.params["defaults_hash"]:
            self.params["defaults_hash"] = ""

    def set_packages_hash(self):
        # sort and deduplicate requested packages
        if "packages" in self.params:
            self.params["packages"] = sorted(list(set(self.params["packages"])))
            self.params["packages_hash"] = get_hash(
                " ".join(self.params["packages"]), 12
            )
        else:
            self.params["packages"] = ""
            self.params["packages_hash"] = ""

    # write buildlog.txt to image dir
    def store_log(self, buildlog):
        self.log.debug("write log")
        with open(self.params["dir"] + "/buildlog.txt", "a") as buildlog_file:
            buildlog_file.writelines(buildlog)

    # return dir where image is stored on server
    def set_image_dir(self):
        path_array = [self.config.get_folder("download_folder")]

        # if custom uci defaults prepand some folders
        if self.params["defaults_hash"]:
            path_array.append("custom")
            path_array.append(self.params["defaults_hash"])

        path_array.extend(
            [
                self.params["distro"],
                self.params["version"],
                self.params["target"],
                self.params["profile"],
                self.params["manifest_hash"],
            ]
        )
        self.params["dir"] = "/".join(path_array)

    # return params of array in specific order
    def as_array(self, extra=None):
        as_array = [
            self.params["distro"],
            self.params["version"],
            self.params["target"],
            self.params["profile"],
            self.params["defaults_hash"],
        ]
        if extra:
            as_array.append(self.params[extra])
        return as_array

    def get_params(self):
        return {
            "distro": self.params["distro"],
            "version": self.params["version"],
            "target": self.params["target"],
            "profile": self.params["profile"],
            "image_hash": self.params["image_hash"],
            "manifest_hash": self.params["manifest_hash"],
            "defaults_hash": self.params["defaults_hash"],
            "worker": self.params["worker"],
            "build_seconds": self.params["build_seconds"],
            "sysupgrade": self.params["sysupgrade"],
        }

    def created(self):
        if os.path.exists(self.params["dir"] + "/sha256sums"):
            return True
        else:
            return False
