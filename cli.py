#!/usr/bin/env python3

import yaml
import json
from shutil import rmtree
import urllib.request
import logging
import argparse
import os
from utils.common import *
from utils.database import Database
from utils.config import Config

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
        parser.add_argument("-f", "--flush-snapshots", action="store_true")
        parser.add_argument("-p", "--parse-configs", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["download_versions"]:
            self.download_versions()
        if self.args["init_server"]:
            self.init_server()
        if self.args["flush_snapshots"]:
            self.flush_snapshots()
        if self.args["parse_configs"]:
            self.insert_board_rename()
            self.load_tables()

    def flush_snapshots(self):
        self.log.info("flush snapshots")
        for distro in self.config.get_distros():
            download_folder = os.path.join(config.get_folder("download_folder"), distro, "snapshot")
            if os.path.exists(download_folder):
                self.log.info("remove snapshots of %s", distro)
                rmtree(download_folder)
        self.database.flush_snapshots()

    def download_versions(self):
        for distro in self.config.get_distros():
            # set distro alias like OpenWrt, fallback would be openwrt
            self.database.insert_distro({
                "name": distro,
                "alias": self.config.get(distro).get("distro_alias", distro),
                "description": self.config.get(distro).get("distro_description", ""),
                "latest": self.config.get(distro).get("latest")
                })
            for version in self.config.get(distro).get("versions", []):
                version_config = self.config.version(distro, version)
                self.database.insert_version({
                    "distro": distro,
                    "version": version,
                    "alias": version_config.get("version_alias", "")
                    "description": version_config.get("version_description", "")
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

                # TODO do this at once instead of per target
                for target in version_targets:
                    self.log.debug("add %s/%s/%s", distro, version, target)
                    self.database.insert_subtarget(distro, version, *target.split("/"))


    def insert_board_rename(self):
        for distro, version in self.database.get_versions():
            version_config = self.config.version(distro, version)
            if "board_rename" in version_config:
                for origname, newname in version_config["board_rename"].items():
                    self.log.info("insert board_rename {} {} {} {}".format(distro, version, origname, newname))
                    self.database.insert_board_rename(distro, version, origname, newname)

    def insert_replacements(self, distro, version, transformations):
        for package, action in transformations.items():
            if not action:
                # drop package
                #print("drop", package)
                self.database.insert_transformation(distro, version, package, None, None)
            elif type(action) is str:
                # replace package
                #print("replace", package, "with", action)
                self.database.insert_transformation(distro, version, package, action, None)
            elif type(action) is dict:
                for choice, context in action.items():
                    if context is True:
                        # set default
                        #print("default", choice)
                        self.database.insert_transformation(distro, version, package, choice, None)
                    elif context is False:
                        # possible choice
                        #print("choice", choice)
                        pass
                    elif type(context) is list:
                        for dependencie in context:
                            # if context package exists
                            #print("dependencie", dependencie, "for", choice)
                            self.database.insert_transformation(distro, version, package, choice, dependencie)

    def load_tables(self):
        for distro, version in self.database.get_versions():
            version = str(version)
            version_replacements_path = os.path.join("distributions", distro, (version + ".yml"))
            if os.path.exists(version_replacements_path):
                with open(version_replacements_path, "r") as version_replacements_file:
                    replacements = yaml.load(version_replacements_file.read())
                    if replacements:
                        if "transformations" in replacements:
                            self.insert_replacements(distro, version, replacements["transformations"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sc = ServerCli()
