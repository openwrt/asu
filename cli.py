#!/usr/bin/env python3

import re
import yaml
import json
from os import makedirs
from shutil import copyfile
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
        parser.add_argument("-a", "--init-all-imagebuilders", action="store_true")
        parser.add_argument("-v", "--build-vanilla", action="store_true")
        parser.add_argument("-r", "--download-releases", action="store_true")
        parser.add_argument("-i", "--init-server", action="store_true")
        parser.add_argument("-f", "--flush-snapshots", action="store_true")
        parser.add_argument("-p", "--parse-configs", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["build_vanilla"]:
            self.build_vanilla()
        if self.args["init_all_imagebuilders"]:
            self.init_all_imagebuilders()
        if self.args["download_releases"]:
            self.download_releases()
        if self.args["init_server"]:
            self.init_server()
        if self.args["flush_snapshots"]:
            self.flush_snapshots()
        if self.args["parse_configs"]:
            self.insert_board_rename()
            self.load_tables()


    def init_all_imagebuilders(self):
        for distro, release in self.database.get_releases():
            if release == 'snapshot' or release == self.config.get(distro).get("latest"):
                subtargets = self.database.get_subtargets(distro, release)
                for target, subtarget, supported in subtargets:
                    self.log.info("requesting {} {} {} {}".format(distro, release, target, subtarget))
                    self.database.imagebuilder_status(distro, release, target, subtarget)

    def build_vanilla(self):
        for distro, release in self.database.get_releases():
            if release == self.config.get(distro).get("latest"):
                subtargets = self.database.get_subtargets(distro, release)
                for target, subtarget, supported in subtargets:
                    sql = """select profile from profiles
                        where distro = ? and
                        release = ? and
                        target = ? and
                        subtarget = ? and
                        profile != 'Default'
                        order by profile desc
                        limit 1;"""
                    profile_request = self.database.c.execute(sql, distro, release, target, subtarget)
                    if self.database.c.rowcount > 0:
                        profile = profile_request.fetchone()[0]

                        conditions = {"distro": distro, "version": release, "target": target, "subtarget": subtarget, "board": profile}
                        self.log.info("request %s", conditions)
                        params = json.dumps(conditions).encode('utf-8')
                        req = urllib.request.Request(
                                self.config.get("update_server") + '/api/build-request',
                                data=params,
                                headers={'content-type': 'application/json'})
                        try:
                            response = urllib.request.urlopen(req)
                            self.log.info(response.read())
                        except:
                            self.log.warning("bad request")
                    else:
                        self.log.warning("no profile found")


    def flush_snapshots(self):
        self.log.info("flush snapshots")
        for distro in self.config.get_distros():
            download_folder = os.path.join(config.get_folder("download_folder"), distro, "snapshot")
            if os.path.exists(download_folder):
                self.log.info("remove snapshots of %s", distro)
                rmtree(download_folder)

        self.database.flush_snapshots()

    def init_server(self):
        usign_init()
        gpg_init()
        #gpg_gen_key("test@test.de")
        copyfile(config.get_folder("keys_private") + "/public", config.get_folder("keys_public") + "/server/etc/server.pub")
        copyfile(config.get_folder("keys_private") + "/public.gpg", config.get_folder("keys_public") + "/server/etc/server.gpg")
        makedirs(config.get_folder("download_folder") + "/faillogs", exist_ok=True)

        # folder to include server keys in created images
        makedirs(config.get_folder("keys_public") + "/server/etc/", exist_ok=True)
        self.download_releases()

    def download_releases(self):
        for distro in self.config.get_distros():
            alias = self.config.get(distro).get("distro_alias")
            self.log.info("set alias %s for %s", distro, alias)
            self.database.set_distro_alias(distro, alias)
            snapshots_url = self.config.get(distro).get("snapshots_url", False)
            if snapshots_url:
                snapshots_url = snapshots_url + "/targets/"
                print("adding snapshots")
                self.database.insert_release(distro, "snapshot")
                target_website = urllib.request.urlopen(snapshots_url).read().decode('utf-8')
                target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                targets = re.findall(target_pattern, target_website)

                for target in targets:
                    subtarget_website = urllib.request.urlopen("{}/{}".format(snapshots_url, target)).read().decode('utf-8')
                    subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                    subtargets = re.findall(subtarget_pattern, subtarget_website)
                    print("snapshots {} {}".format("snapshot", target, subtargets))
                    self.database.insert_subtargets(distro, "snapshot", target, subtargets)

            releases_url = self.config.get(distro).get("releases_url", False)
            if releases_url:
                for release in self.config.get(distro).get("releases"):
                    print("{} {}".format(distro, release))
                    self.database.insert_release(distro, release)
                    release_url = "{}/{}/targets/".format(releases_url, release)
                    if get_statuscode(release_url) != 404:
                        print("release {} online".format(release))
                        targets_website = urllib.request.urlopen(release_url).read().decode('utf-8')
                        targets_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                        targets = re.findall(targets_pattern, targets_website)
                        for target in targets:
                            subtargets_website = urllib.request.urlopen("{}/{}/targets/{}".format(releases_url, release, target)).read().decode('utf-8')
                            subtargets_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                            subtargets = re.findall(subtargets_pattern, subtargets_website)
                            print("{} {} {}".format(release, target, subtargets))
                            self.database.insert_subtargets(distro, release, target, subtargets)
                    else:
                        print("release {} offline".format(release))

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

logging.basicConfig(level=logging.DEBUG)
sc = ServerCli()
#sc.database.imagebuilder_status("test", "17.01.4", "x86", "64")
