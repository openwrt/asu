import yaml
import os.path
from shutil import copyfile

class Config():
    def __init__(self, config_file="config.yml"):
        self.config = {}

        if not os.path.exists(config_file):
            copyfile((config_file + ".default"), config_file)
            
        with open(config_file, 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

    def get_all(self):
        return self.config

    def get(self, option):
        if option in self.config:
            return self.config[option]
        else:
            return None

if __name__ == "__main__":
    config = Config()
    print(config.get("update_server"))
