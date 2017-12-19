import yaml
import os.path
from shutil import copyfile

class Config():
    def __init__(self, config_file="config.yml"):
        self.config = {}
        self.config_file = config_file

        if not os.path.exists(self.config_file):
            copyfile(("config.yml.default"), self.config_file)

        with open(self.config_file, 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

        for distro in os.listdir("distributions"):
            with open(os.path.join("distributions", distro, "distro_config.yml"), 'r') as ymlfile:
                self.config[distro] = yaml.load(ymlfile)

            if self.config.get(distro).get("releases"):
                self.config[distro]["latest"] = self.config.get(distro).get("releases")[-1]
            else:
                self.config[distro]["latest"] = None

    def release(self, distro, release):
        if release not in self.config[distro]:
            with open(os.path.join("distributions", distro, release + ".yml"), 'r') as ymlfile:
               self.config[distro][release] = yaml.load(ymlfile)
        return self.config.get(distro).get(release)

    def get(self, opt, alt=None):
        if opt in self.config:
            return self.config[opt]
        return alt
