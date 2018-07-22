#!/usr/bin/env python3

import re
import yaml
import json
from os import makedirs
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
        parser.add_argument("-r", "--download-releases", action="store_true")
        parser.add_argument("-i", "--init-server", action="store_true")
        parser.add_argument("-f", "--flush-snapshots", action="store_true")
        parser.add_argument("-p", "--parse-configs", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["download_releases"]:
            self.download_releases()
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

    def download_releases(self):
        for distro in self.config.get_distros():
            for release in self.config.get(distro).get("releases", []):
                self.database.insert_release(distro, release)
                release_url = self.config.release(distro, release).get("targets_url")

                release_targets = json.loads(urllib.request.urlopen(
                    "{}/{}/targets?json-targets".format(release_url, release))
                        .read().decode('utf-8'))
                self.log.info("add %s/%s targets", distro, release)

                # TODO do this at once instead of per target
                for target in release_targets:
                    self.database.insert_subtarget(distro, release, *target.split("/"))

            # set distro alias like OpenWrt, fallback would be openwrt
            self.database.set_distro_alias(distro, self.config.get(distro).get("distro_alias", distro))

    def insert_board_rename(self):
        for distro, release in self.database.get_releases():
            release_config = self.config.release(distro, release)
            if "board_rename" in release_config:
                for origname, newname in release_config["board_rename"].items():
                    self.log.info("insert board_rename {} {} {} {}".format(distro, release, origname, newname))
                    self.database.insert_board_rename(distro, release, origname, newname)

    def insert_replacements(self, distro, release, transformations):
        for package, action in transformations.items():
            if not action:
                # drop package
                #print("drop", package)
                self.database.insert_transformation(distro, release, package, None, None)
            elif type(action) is str:
                # replace package
                #print("replace", package, "with", action)
                self.database.insert_transformation(distro, release, package, action, None)
            elif type(action) is dict:
                for choice, context in action.items():
                    if context is True:
                        # set default
                        #print("default", choice)
                        self.database.insert_transformation(distro, release, package, choice, None)
                    elif context is False:
                        # possible choice
                        #print("choice", choice)
                        pass
                    elif type(context) is list:
                        for dependencie in context:
                            # if context package exists
                            #print("dependencie", dependencie, "for", choice)
                            self.database.insert_transformation(distro, release, package, choice, dependencie)

    def load_tables(self):
        for distro, release in self.database.get_releases():
            release = str(release)
            release_replacements_path = os.path.join("distributions", distro, (release + ".yml"))
            if os.path.exists(release_replacements_path):
                with open(release_replacements_path, "r") as release_replacements_file:
                    replacements = yaml.load(release_replacements_file.read())
                    if replacements:
                        if "transformations" in replacements:
                            self.insert_replacements(distro, release, replacements["transformations"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sc = ServerCli()
