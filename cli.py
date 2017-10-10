#!/usr/bin/env python3

import re
import yaml
from shutil import rmtree
import urllib.request
import logging
import argparse
import os
from utils.common import get_supported_targets, get_dir, get_statuscode, get_releases, get_latest_release
from utils.database import Database
from utils.config import Config

class ServerCli():
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.config = Config()
        self.init_args()

    def init_args(self):
        parser = argparse.ArgumentParser(description="CLI for update-server")
        parser.add_argument("-a", "--init-all-imagebuilders", action="store_true")
        parser.add_argument("-r", "--download-releases", action="store_true")
        parser.add_argument("-u", "--update-packages", action="store_true")
        parser.add_argument("-c", "--update-repositories", action="store_true")
        parser.add_argument("-s", "--set-supported", action="store_true")
        parser.add_argument("-f", "--flush-snapshots", action="store_true")
        parser.add_argument("--ignore-not-supported", action="store_true")
        parser.add_argument("-t", "--parse-transformations", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["init_all_imagebuilders"]:
            self.init_all_imagebuilders()
        if self.args["download_releases"]:
            self.download_releases()
        if self.args["set_supported"]:
            self.set_supported()
        if self.args["flush_snapshots"]:
            self.flush_snapshots()
        if self.args["parse_transformations"]:
            self.load_tables()

    def init_all_imagebuilders(self):
        for distro, release in self.database.get_releases():
            if release == 'snapshot' or release == get_latest_release(distro):
                subtargets = self.database.get_subtargets(distro, release)
                for target, subtarget, supported in subtargets:
                    if supported:
                        self.log.info("requesting {} {} {} {}".format(distro, release, target, subtarget))
                        self.database.imagebuilder_status(distro, release, target, subtarget)

    def flush_snapshots(self):
        self.log.info("flush snapshots")
        self.database.flush_snapshots()
        workdir = os.path.join(get_dir("workdir"), "lede", "snapshot")
        if os.path.exists(workdir):
            self.log.info("remove snapshots imagebuidler")
            rmtree(workdir)
        downloaddir = os.path.join(get_dir("downloaddir"), "lede", "snapshot")

        if os.path.exists(downloaddir):
            self.log.info("remove snapshots images")
            rmtree(downloaddir)

    def set_supported(self):
        for distro, release in self.database.get_releases():
            supported = get_supported_targets(distro, release)
            if supported:
                for target, subtargets in supported.items():
                    if not subtargets:
                        self.database.insert_supported(distro, release, target)
                    else:
                        for subtarget in subtargets:
                            self.database.insert_supported(distro, release, target, subtarget)

    def download_releases(self):
        if self.config.get("snapshots"):
            print("adding lede snapshots")
            self.database.insert_release("lede", "snapshot")
            snapshots_url = "http://downloads.lede-project.org/snapshots/targets/"
            target_website = urllib.request.urlopen(snapshots_url).read().decode('utf-8')
            target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
            targets = re.findall(target_pattern, target_website)

            for target in targets:
                subtarget_website = urllib.request.urlopen("{}/{}".format(snapshots_url, target)).read().decode('utf-8')
                subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                subtargets = re.findall(subtarget_pattern, subtarget_website)
                print("snapshots {} {}".format("snapshots", target, subtargets))
                self.database.insert_subtargets("lede", "snapshot", target, subtargets)

        for distro, distro_url in self.config.get("distributions").items():
            #print("searching {} releases".format(distro))
            #releases_website = urllib.request.urlopen(distro_url).read().decode('utf-8')
            #releases_pattern = r'href="(.+?)/?">.+/?</a>/?</td>'
            #releases = re.findall(releases_pattern, releases_website)
            for release in get_releases(distro):
                release = str(release)
                print("{} {}".format(distro, release))
                self.database.insert_release(distro, release)
                release_url = "{}/{}/targets/".format(distro_url, release)
                if get_statuscode(release_url) != 404:
                    print("release {} online".format(release))
                    targets_website = urllib.request.urlopen(release_url).read().decode('utf-8')
                    targets_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                    targets = re.findall(targets_pattern, targets_website)
                    for target in targets:
                        subtargets_website = urllib.request.urlopen("{}/{}/targets/{}".format(distro_url, release, target)).read().decode('utf-8')
                        subtargets_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                        subtargets = re.findall(subtargets_pattern, subtargets_website)
                        print("{} {} {}".format(release, target, subtargets))
                        self.database.insert_subtargets(distro, release, target, subtargets)
                else:
                    print("release {} offline".format(release))

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
        distros = {}
        for distro in self.config.get("distributions").keys():
            distros[distro] = {}
            releases = yaml.load(open(os.path.join("distributions", distro, "releases.yml")).read())
            for release in releases:
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

