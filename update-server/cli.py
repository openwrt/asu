from database import Database
import re
import urllib.request
import logging
from config import Config
from imagebuilder import ImageBuilder
import argparse

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
        parser.add_argument("-a", "--setup-all-imagebuilders", action="store_true")
        args = vars(parser.parse_args())
        if args["download_releases"]:
            self.download_releases()
        if args["download_targets"]:
            self.download_targets()
        if args["setup_all_imagebuilders"]:
            self.setup_all_imagebuilders()
        if args["setup_imagebuilder"]:
            self.setup_imagebuilder(*args["setup_imagebuilder"])

    def setup_all_imagebuilders(self):
        print("init all imagebuilders")
        for distro, release in self.database.get_releases():
            targets = self.database.get_targets(distro, release)
            for target, subtarget in targets:
                self.setup_imagebuilder(distro, release, target, subtarget)

    def setup_imagebuilder(self, distro, version, target, subtarget):
        ib = ImageBuilder(distro, version, target, subtarget)
        if not ib.created():
            print("could not found imagebuilder for {} {} {} - downloading...".format(version, target,         subtarget))
            if not ib.setup():
                print("download failed")
            print("downloaded imagebuilder {} - initiating".format(ib.path))
            print("downloaded {}".format(ib.path))
        else:
            print("found imagebuilder {}".format(ib.path))
        print("initianiting")
        ib.run()
        print("initiaded")


    def download_releases(self):
        for distro, distro_url in self.config.get("distributions").items():
            print("searing {} releases".format(distro))
            releases_website = urllib.request.urlopen(distro_url).read().decode('utf-8')
            releases_pattern = r'href="(.+?)/?">.+/?</a>/?</td>'
            releases = re.findall(releases_pattern, releases_website)
            for release in releases:
                # need a better regex here
                if release != ".." and not release.startswith("packages") and not "rc" in release and not "/" == release and not release == "current":
                    print("{} {}".format(distro, release))
                    self.database.insert_release(distro, release)

    def download_targets(self):
        for distro, release in self.database.get_releases():
            distro_url = self.config.get("distributions")[distro]
#            http://repo.libremesh.org/lime-17.04/targets/
            target_website = urllib.request.urlopen("{}/{}/targets/".format(distro_url, release)).read().decode('utf-8')
            # <a href="lantiq/">lantiq/</a></td>
            target_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
            targets = re.findall(target_pattern, target_website)

            for target in targets:
                subtarget_website = urllib.request.urlopen("{}/{}/targets/{}".format(distro_url, release, target)).read().decode('utf-8')
                subtarget_pattern = r'<a href="(\w+?)/?">.+?/?</a>/?</td>'
                subtargets = re.findall(subtarget_pattern, subtarget_website)
                print("{} {} {}".format(release, target, subtargets))
                self.database.insert_target(distro, release, target, subtargets)




logging.basicConfig(level=logging.DEBUG)
sc = ServerCli()

