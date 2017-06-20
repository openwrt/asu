from database import Database
import re
import urllib.request
from imagebuilder import ImageBuilder

class ServerCli():
    def __init__(self):
        self.database = Database()
        self.distro_urls = {"lede": "https://downloads.lede-project.org/"}


    def init_all_imagebuilders(self):
        print("init all imagebuilders")
        targets = self.database.get_targets()
        for version in self.releases:
            for target, subtarget in targets:
                ib = ImageBuilder("lede", version, target, subtarget)
                if not ib.created():
                    print("could not found imagebuilder for {} {} {} - downloading...".format(version, target,         subtarget))
                    if not ib.download():
                        print("download failed")
                        continue
                    print("downloaded imagebuilder {} - initiating".format(ib.path))
                    print("initiated {}".format(ib.path))
                else:
                    print("found imagebuilder {}".format(ib.path))
                ib.run()

    def download_releases(self):
        for distro, distro_url in self.distro_urls.items():
            releases_website = urllib.request.urlopen("{}/releases/".format(distro_url)).read().decode('utf-8')
            releases_pattern = r'<tr><td class="n"><a href=".+">(.+)</a>/</td><td class="s">-</td><td class="d">.+</td></tr>'
            releases = re.findall(releases_pattern, releases_website)
            for release in releases:
                if release != ".." and not release.startswith("packages") and not "rc" in release:
                    print("{} {}".format(distro, release))
                    self.database.insert_release(distro, release)

    def download_targets(self):
        for distro, release in self.database.get_releases():
            distro_url = self.distro_urls[distro]
            target_website = urllib.request.urlopen("{}/releases/{}/targets/".format(distro_url, release)).read().decode('utf-8')
            target_pattern = r'<tr><td class="n"><a href=".+">(\w+)</a>/</td><td class="s">-</td><td class="d">.+</td></tr>'
            targets = re.findall(target_pattern, target_website)

            for target in targets:
                subtarget_website = urllib.request.urlopen("{}/releases/{}/targets/{}".format(distro_url, release, target)).read().decode('utf-8')
                subtarget_pattern = r'<tr><td class="n"><a href=".+">(\w+)</a>/</td><td class="s">-</td><td class="d">.+</td></tr>'
                subtargets = re.findall(subtarget_pattern, subtarget_website)
                print("{} {} {}".format(release, target, subtargets))
                self.database.insert_target(distro, release, target, subtargets)




sc = ServerCli()
sc.download_releases()
sc.download_targets()

