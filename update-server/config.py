import yaml
import os.path
from shutil import copyfile

class Config():
    def __init__(self):
        self.config = {}

        if not os.path.exists("config.yml"):
            copyfile("config.yml.default", "config.yml")
            
        with open("config.yml", 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

    def get(self, option):
        if option in self.config:
            return self.config[option]
        else:
            return None

if __name__ == "__main__":
    config = Config()
    print(config.get("update_server"))
