from database import Database
import re
import urllib.request
import logging
from config import Config
from imagebuilder import ImageBuilder
import argparse
from util import get_supported_targets

class ServerCli():
    def __init__(self):
        self.database = Database()
        self.config = Config()
        self.init_args()

    def init_args(self):
        parser = argparse.ArgumentParser(description="CLI for update-server")
        parser.add_argument("-r", "--download-releases", action="store_true")
        parser.add_argument("-t", "--download-targets", action="store_true")
        parser.add_argument("-i", "--setup-imagebuilder", nargs="+")
        parser.add_argument("-a", "--setup-all-imagebuilders", nargs="*")
        parser.add_argument("-u", "--update-packages", action="store_true")
        parser.add_argument("-c", "--update-repositories", action="store_true")
        parser.add_argument("-s", "--set-supported", action="store_true")
        parser.add_argument("--ignore-not-supported", action="store_true")
        parser.add_argument("--add-snapshots", action="store_true")
        self.args = vars(parser.parse_args())
        if self.args["download_releases"]:
            self.download_releases()
        if self.args["download_targets"]:
            self.download_targets()
        if self.args["setup_all_imagebuilders"]:
            self.setup_all_imagebuilders(*self.args["setup_all_imagebuilders"])
        if self.args["setup_imagebuilder"]:
            self.setup_imagebuilder(*self.args["setup_imagebuilder"])
        if self.args["set_supported"]:
            self.set_supported()
        if self.args["add_snapshots"]:
            self.add_snapshots()

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

    def setup_all_imagebuilders(self, *args):
        if not args:
            print("init all imagebuilders")
        else:
            print("init imagebuilder {}".format(args))
        for distro, release in self.database.get_releases():
            if len(args) > 0:
                if distro != args[0]:
                    continue
            if len(args) > 1:
                if release != args[1]:
                    continue
            targets = self.database.get_targets(distro, release)
            for target, subtarget, supported in targets:
                if len(args) > 2:
                    if target != args[2]:
                        continue
                if len(args) > 3:
                    if subtarget != args[3]:
                        continue
                if supported == "1" or self.args["ignore_not_supported"]: 
                    self.setup_imagebuilder(distro, release, target, subtarget)
                else:
                    print("target {} not supported for sysupgrade, skipping".format(target))

    def setup_imagebuilder(self, distro, version, target, subtarget):
        ib = ImageBuilder(distro, version, target, subtarget)
        if not ib.created():
            print("downloaded imagebuilder {} - initiating".format(ib.path))
            ib.run()
            print("initiaded")
        else:
            print("found imagebuilder {}".format(ib.path))
        if self.args["update_repositories"]:
            ib.add_custom_repositories()
        if self.args["update_packages"]:
            ib.parse_packages()

    def download_releases(self):

        for distro, distro_url in self.config.get("distributions").items():
            print("searing {} releases".format(distro))
            releases_website = urllib.request.urlopen(distro_url).read().decode('utf-8')
            releases_pattern = r'href="(.+?)/?">.+/?</a>/?</td>'
            releases = re.findall(releases_pattern, releases_website)
            for release in releases:
                # need a better regex here
                if release != ".." and not release.startswith("packages") and not "rc" in release and not "/" == release and not release == "current" and not release == "lime-16.07":
                    print("{} {}".format(distro, release))
                    self.database.insert_release(distro, release)
                    target_website = urllib.request.urlopen("{}/{}/targets/".format(distro_url, release)).read().decode('utf-8')
                    target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                    targets = re.findall(target_pattern, target_website)
                    for target in targets:
                        subtarget_website = urllib.request.urlopen("{}/{}/targets/{}".format(distro_url, release, target)).read().decode('utf-8')
                        subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                        subtargets = re.findall(subtarget_pattern, subtarget_website)
                        print("{} {} {}".format(release, target, subtargets))
                        self.database.insert_target(distro, release, target, subtargets)

    def download_targets(self):
        for distro, release in self.database.get_releases():
            if release == "lede" and release == "snapshots":
                continue
            distro_url = self.config.get("distributions")[distro]
            target_website = urllib.request.urlopen("{}/{}/targets/".format(distro_url, release)).read().decode('utf-8')
            target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
            targets = re.findall(target_pattern, target_website)

            for target in targets:
                subtarget_website = urllib.request.urlopen("{}/{}/targets/{}".format(distro_url, release, target)).read().decode('utf-8')
                subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                subtargets = re.findall(subtarget_pattern, subtarget_website)
                print("{} {} {}".format(release, target, subtargets))
                self.database.insert_target(distro, release, target, subtargets)    

    def add_snapshots(self):
        print("adding lede snapshots")
        self.database.insert_release("lede", "snapshots")
        snapshots_url = "http://downloads.lede-project.org/snapshots/targets/"
        target_website = urllib.request.urlopen(snapshots_url).read().decode('utf-8')
        target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
        targets = re.findall(target_pattern, target_website)

        for target in targets:
            subtarget_website = urllib.request.urlopen("{}/{}".format(snapshots_url, target)).read().decode('utf-8')
            subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
            subtargets = re.findall(subtarget_pattern, subtarget_website)
            print("snapshots {} {}".format("snapshots", target, subtargets))
            self.database.insert_target("lede", "snapshots", target, subtargets)    

logging.basicConfig(level=logging.DEBUG)
sc = ServerCli()

