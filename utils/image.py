from utils.common import get_hash
from utils.config import Config
from utils.database import Database

class Image():
    def __init__(self, params):
        self.params = params

        # sort and deduplicate requested packages
        self.params["packages"] = sorted(list(set(self.params["packages"])))

        # create hash of requested packages and store in database
        self.params["package_hash"] = get_hash(" ".join(self.params["packages"]), 12)
        self.database.insert_hash(self.params["package_hash"], self.params["packages"])

    # write buildlog.txt to image dir
    def store_log(self, buildlog):
        self.log.debug("write log")
        with open(self.params["dir"] + "/buildlog.txt", "a") as buildlog_file:
            buildlog_file.writelines(buildlog)

    # parse created manifest and add to database, returns hash of manifest file
    def set_manifest_hash(self):
        manifest_path = glob.glob(self.params["dir"] + "/*.manifest")[0]
        with open(manifest_path, 'rb') as manifest_file:
            self.params["manifest_hash"] = hashlib.sha256(manifest_file.read()).hexdigest()[0:15]
            
        manifest_pattern = r"(.+) - (.+)\n"
        with open(manifest_path, "r") as manifest_file:
            manifest_packages = dict(re.findall(manifest_pattern, manifest_file.read()))
            self.database.add_manifest_packages(self.params["manifest_hash"], manifest_packages)

    def set_image_hash(self):
        self.params["image_hash"] = get_hash(" ".join(self.as_array("manifest_hash"), 15))

    def set(self, key, value):
        self.params[key] = value

    def get(self, key):
        return self.params.get(key)

    # return dir where image is stored on server
    def set_image_dir(self):
        self.params["dir"] = "/".join([
            self.config.get_folder("download_folder"),
            self.params["distro"],
            self.params["release"],
            self.params["target"],
            self.params["subtarget"],
            self.params["profile"],
            self.params["manifest_hash"]
            ])
        return self.params["dir"]


    # return params of array in specific order
    def as_array(self, extra=None):
        as_array= [
            self.params["distro"],
            self.params["release"],
            self.params["target"],
            self.params["subtarget"],
            self.params["profile"]
            ]
        if extra:
            as_array.append(self.params[extra])
        return as_array

    def get_params(self):
        return self.params
