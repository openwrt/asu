import yaml
import shutil
import os.path
import json
import os


class Config:
    """Config of the asu server and worker"""

    config = {}
    root_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = "/etc/asu/config.yml"

    def __init__(self):
        if not os.path.exists(self.config_file):
            self.config_file = "config.yml"
            if not os.path.exists(self.config_file):
                with open(self.root_dir + "/config.yml.default", "r") as default_file:
                    with open("config.yml", "w") as config_file:
                        config_file.write(default_file.read())

        with open(self.config_file, "r") as ymlfile:
            self.config = yaml.safe_load(ymlfile)

        distro_folder = self.config.get("distro_folder")
        if not os.path.exists(distro_folder):
            shutil.copytree(self.root_dir + "/distributions", distro_folder)

        # load configuration of distro and overlay it with custom version settings
        self.config["distros"] = {}
        # load config for all active_distros
        for distro in self.get_distros():
            self.config["distros"][distro] = {}
            base_path = self.get_folder("distro_folder") + "/" + distro
            # load distro_config.yml
            with open(base_path + "/distro_config.yml", "r") as distro_file:
                self.config["distros"][distro] = yaml.safe_load(distro_file.read())
                self.config["distros"][distro].pop("version_common", None)
            distro_versions = self.config["distros"][distro]["versions"].copy()
            self.config["distros"][distro]["versions"] = {}
            # load all versions of distro_config
            for version in distro_versions:
                with open(base_path + "/distro_config.yml", "r") as distro_file:
                    self.config["distros"][distro]["versions"][
                        version
                    ] = yaml.safe_load(distro_file.read()).get("version_common", {})
                version_path = os.path.join(base_path, version + ".yml")
                if os.path.exists(version_path):
                    with open(version_path, "r") as version_file:
                        self.config["distros"][distro]["versions"][version].update(
                            yaml.safe_load(version_file.read())
                        )

    def get_distros(self):
        return self.config.get("active_distros", ["openwrt"])

    def version(self, distro, version):
        return self.config["distros"][distro]["versions"][version]

    def get(self, opt, alt=None):
        if opt in self.config:
            return self.config[opt]
        return alt

    def get_folder(self, requested_folder):
        folder = self.config.get(requested_folder)
        if folder:
            if not os.path.exists(folder):
                os.makedirs(folder)
            return os.path.abspath(folder)
        else:
            raise Exception("Folder {} not set".format(requested_folder))

    def as_json(self):
        return json.dumps(self.config["distros"])
