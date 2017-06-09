import yaml

class Config():
    def __init__(self):
        self.config = {}

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
