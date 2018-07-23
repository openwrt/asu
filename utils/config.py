import yaml
import os.path
import os
from os import listdir, makedirs
from shutil import copyfile

class Config():
    def __init__(self):
        self.config = {}
        self.config_file = "config.yml"

        if not os.path.exists(self.config_file):
            print("Missing config.yml")
            exit(1)

        with open(self.config_file, 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

        for distro in self.get_distros():
            with open(os.path.join(self.get_folder("distro_folder"), distro, "distro_config.yml"), 'r') as ymlfile:
                self.config[distro] = yaml.load(ymlfile)

            if self.config.get(distro).get("versions"):
                self.config[distro]["latest"] = self.config.get(distro).get("versions")[-1]
            else:
                self.config[distro]["latest"] = None

    def version(self, distro, version):
        version_config = {}
        base_path = self.get_folder("distro_folder") + "/" + distro

        with open(base_path + "/distro_config.yml", 'r') as distro_file:
            version_config.update(yaml.load(distro_file.read()))


        version_path = os.path.join(base_path, distro, version + ".yml")
        if os.path.exists(version_path):
            with open(version_path, 'r') as version_file:
                version_content = yaml.load(version_file.read())
                if version_content:
                    version_config.update(version_content)

        return version_config

    def get(self, opt, alt=None):
        if opt in self.config:
            return self.config[opt]
        return alt

    def get_folder(self, requested_folder):
        folder = self.config.get(requested_folder)
        if folder:
            if not os.path.exists(folder): os.makedirs(folder)
            return os.path.abspath(folder)

        # if unset use $PWD/<requested_folder>
        default_folder = os.path.join(os.getcwdb(), requested_folder)
        if not os.path.exists(default_folder): makedirs(default_folder)
        return os.path.abspath(default_folder)

    def get_distros(self):
        return(listdir(self.config.get("distro_folder")))
