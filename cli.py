#!/usr/bin/env python3

import yaml
import json
from shutil import rmtree
import urllib.request
import logging
import argparse
import os
from asu.utils.common import *
from asu.utils.database import Database
from asu.utils.config import Config

class ServerCli():
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.database = Database(self.config)
        self.init_args()

    def init_args(self):
        parser = argparse.ArgumentParser(description="CLI for update-server")
        parser.add_argument("-r", "--download-versions", action="store_true")
        parser.add_argument("-i", "--init-server", action="store_true")
        parser.add_argument("-p", "--parse-configs", action="store_true")
        parser.add_argument("-w", "--create-worker", action="store_true")
        parser.add_argument("-a", "--create-all", action="store_true")
        parser.add_argument("-d", "--init-db", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["download_versions"]:
            self.download_versions()
        if self.args["init_server"]:
            self.download_versions()
            self.load_tables()
            self.insert_board_rename()
        if self.args["parse_configs"]:
            self.insert_board_rename()
            self.load_tables()
        if self.args["create_worker"]:
            self.create_worker_image()
        if self.args["create_all"]:
            self.create_all_profiles()
        if self.args["init_db"]:
            self.init_db()

    def create_all_profiles(self):
        for profile in self.database.get_all_profiles():
            target, subtarget, board = profile
            image_params = {
                "distro": "openwrt",
                "version": "18.06.1",
                "target": target,
                "subtarget": subtarget,
                "board": board
                }
            params = json.dumps(image_params).encode('utf8')
            req = urllib.request.Request(self.config.get("server") +
                    "/api/build-request", data=params,
                    headers={'content-type': 'application/json'} )
            urllib.request.urlopen(req)

    def create_worker_image(self):
        self.log.info("build worker image")
        packages = ["bash", "bzip2", "coreutils", "coreutils-stat",
                "diffutils", "file", "gawk", "gcc", "getopt", "git",
                "libncurses", "make", "patch", "perl", "perlbase-attributes",
                "perlbase-findbin", "perlbase-getopt", "perlbase-thread",
                "python-light", "tar", "unzip", "wget", "xz", "xzdiff",
                "xzgrep", "xzless", "xz-utils", "zlib-dev"]
        image_params = {
            "distro": "openwrt",
            "version": self.config.get("openwrt").get("latest"),
            "target": "x86",
            "subtarget": "64",
            "board": "Default",
            "packages": packages
            }

        params = json.dumps(image_params).encode('utf8')
        req = urllib.request.Request(self.config.get("server") +
                "/api/build-request", data=params,
                headers={'content-type': 'application/json'} )
        response = urllib.request.urlopen(req)
        self.log.info("response: %s", response)

    def download_versions(self):
        for distro in self.config.get("active_distros", ["openwrt"]):
            # set distro alias like OpenWrt, fallback would be openwrt
            self.database.insert_dict("distros", {
                "distro": distro,
                "distro_alias": self.config.get(distro).get("distro_alias", distro),
                "distro_description": self.config.get(distro).get("distro_description", ""),
                "latest": self.config.get(distro).get("latest")
                })
            for version in self.config.get(distro).get("versions", []):
                version_config = self.config.version(distro, version)
                self.database.insert_dict("versions", {
                    "distro": distro,
                    "version": version,
                    "version_alias": version_config.get("version_alias", version),
                    "version_description": version_config.get("version_description", ""),
                    "snapshots": version_config.get("snapshots", False)
                    })
                version_config = self.config.version(distro, version)
                version_url = version_config.get("targets_url")
                # use parent_version for ImageBuilder if exists
                version_imagebuilder = version_config.get("parent_version", version)

                version_targets = set(json.loads(urllib.request.urlopen(
                    "{}/{}/targets?json-targets".format(version_url,
                        version_imagebuilder)).read().decode('utf-8')))

                if version_config.get("active_targets"):
                    version_targets = version_targets & set(version_config.get("active_targets"))

                if version_config.get("ignore_targets"):
                    version_targets = version_targets - set(version_config.get("ignore_targets"))
                
                self.log.info("add %s/%s targets", distro, version)
                self.database.insert_target(distro, version, version_targets)

    def insert_board_rename(self):
        for distro, version in self.database.get_versions():
            version_config = self.config.version(distro, version)
            if "board_rename" in version_config:
                for origname, newname in version_config["board_rename"].items():
                    self.log.info("insert board_rename {} {} {} {}".format(distro, version, origname, newname))
                    self.database.insert_board_rename(distro, version, origname, newname)

    def insert_transformations(self, distro, version, transformations):
        for package, action in transformations.items():
            if not action:
                # drop package
                #print("drop", package)
                self.database.insert_transformation(distro, version, package, None, None)
            elif isinstance(action, str):
                # replace package
                #print("replace", package, "with", action)
                self.database.insert_transformation(distro, version, package, action, None)
            elif isinstance(action, dict):
                for choice, context in action.items():
                    if context is True:
                        # set default
                        #print("default", choice)
                        self.database.insert_transformation(distro, version, package, choice, None)
                    elif context is False:
                        # possible choice
                        #print("choice", choice)
                        # TODO
                        pass
                    elif isinstance(context, list):
                        for dependencie in context:
                            # if context package exists
                            #print("dependencie", dependencie, "for", choice)
                            self.database.insert_transformation(distro, version, package, choice, dependencie)

    def load_tables(self):
        for distro, version in self.database.get_versions():
            self.log.debug("load tables %s %s", distro, version)
            version_transformations_path = os.path.join("distributions", distro, (version + ".yml"))
            if os.path.exists(version_transformations_path):
                with open(version_transformations_path, "r") as version_transformations_file:
                    transformations = yaml.load(version_transformations_file.read())
                    if transformations:
                        if "transformations" in transformations:
                            self.insert_transformations(distro, version, transformations["transformations"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sc = ServerCli()
