import yaml
import os.path
import json
import os
from os import listdir, makedirs

class Config():
    def __init__(self):
        self.config = {}
        self.config_file = "config.yml"
        if not os.path.exists(self.config_file):
            with open(os.path.dirname(os.path.abspath(__file__)) +
                    "/config.yml.default", "r") as default_file:
                with open("config.yml", "w") as config_file:
                    config_file.write(default_file.read())

        with open(self.config_file, 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

        for distro in self.get_distros():
            with open(os.path.join(self.get_folder("distro_folder"), 
                    distro, "distro_config.yml"), 'r') as ymlfile:
                self.config[distro] = yaml.load(ymlfile)

    # load configuration of distro and overlay it with custom version settings
    def version(self, distro, version):
        version_config = {}
        base_path = self.get_folder("distro_folder") + "/" + distro

        with open(base_path + "/distro_config.yml", 'r') as distro_file:
            version_config.update(yaml.load(distro_file.read()))

        version_path = os.path.join(base_path, version + ".yml")
        if os.path.exists(version_path):
            with open(version_path, 'r') as version_file:
                version_content = yaml.load(version_file.read())
                if version_content:
                    version_config.update(version_content)

        # if distro is based on another distro, load these settings as well
        if "parent_version" in version_config:
            parent_config = self.version(
                    version_config["parent_distro"],
                    version_config["parent_version"])

            parent_config.update(version_config)
            return parent_config

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

    def get_all(self):
        distros = {}
        for distro in self.get_distros():
            base_path = self.get_folder("distro_folder") + "/" + distro
            with open(base_path + "/distro_config.yml", 'r') as distro_file:
                distros[distro] = yaml.load(distro_file.read())
            distro_versions = distros[distro]["versions"].copy()
            distros[distro]["versions"] = {}
            for version in distro_versions:
                version_path = os.path.join(base_path, version + ".yml")
                if os.path.exists(version_path):
                    with open(version_path, 'r') as version_file:
                        version_content = yaml.load(version_file.read())
                        if version_content:
                            distros[distro]["versions"][version] = version_content
                else:
                    distros[distro]["versions"][version] = {}
        return json.dumps(distros)

    def get_distros(self):
        return(listdir(self.config.get("distro_folder")))
