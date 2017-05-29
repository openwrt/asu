import tarfile
import shutil
import urllib.request
import tempfile
import logging
import hashlib
import os
import os.path
import subprocess

#logging.basicConfig(filename="output.log")
logging.basicConfig(level=logging.DEBUG)


class Image():
    # distro
    # version
    # target
    # subtarget
    # profile
    # packages
    def __init__(self):
        pass

    def _set_path(self):
        self.pkgHash = self.getPkgHash()

        # using lede naming convention
        path_array = [self.distro, self.version, self.pkgHash, self.target, self.subtarget]
        if self.profile:
            path_array.append(self.profile)

        if self.target != "x86":
            path_array.append("sysupgrade.bin")
        else:
            path_array.append("sysupgrade.img")

        self.name = "-".join(path_array)
        self.path = os.path.join("download", self.distro, self.version, self.target, self.subtarget, self.name)

    def request_variables(self, distro, version, target, subtarget, profile, packages):
        self.distro = distro.lower()
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.profile = profile
        self.packages = packages
        self._set_path()
   
    def request_params(self, params):
        self.distro = params["distro"].lower()
        self.version = params["version"]
        self.target = params["target"]
        self.subtarget = params["subtarget"]
        self.profile = params["profile"]
        self.packages = params["packages"]
        self._set_path()

    # returns the path of the created image
    def get(self):
        if not self.created():
            logging.info("start build")	
            self.build() 
        else:
            print("Heureka!")
        return self.path

    # generate a hash of the installed packages
    def getPkgHash(self):
        packagesSorted = sorted(self.packages)
        h = hashlib.sha256()
        h.update(bytes(" ".join(packagesSorted), 'utf-8'))

        return h.hexdigest()[:12]

    # builds the image with the specific packages at output path
    def build(self):
        # create image path
        ibPath = os.path.abspath(os.path.join("imagebuilder", self.distro, self.target, self.subtarget))
        imagebuilder = ImageBuilder(self.distro, self.version, self.target, self.subtarget)

        logging.info("use imagebuilder at %s", imagebuilder.path)

        buildPath = os.path.dirname(self.path)
        with tempfile.TemporaryDirectory() as buildPath:
    #        print(buildPath)

            create_folder(os.path.dirname(self.path))

            cmdline = ["make", "image"]
            cmdline.append("PROFILE=%s" % self.profile)
            cmdline.append("PACKAGES=%s" % " ".join(self.packages))
            #cmdline.append("BIN_DIR=%s" % os.path.abspath(buildPath))
            cmdline.append("BIN_DIR=%s" % buildPath)
            cmdline.append("EXTRA_IMAGE_NAME=%s" % self.pkgHash)

            logging.info("start build: %s", " ".join(cmdline))

            proc = subprocess.Popen(
                cmdline,
                cwd=imagebuilder.path,
                stdout=subprocess.PIPE,
                shell=False,
                stderr=subprocess.STDOUT
            )

            output, erros = proc.communicate()
            returnCode = proc.returncode
            if returnCode == 0:
                for sysupgrade in os.listdir(buildPath):
                    if sysupgrade.endswith("combined-squashfs.img") or sysupgrade.endswith("sysupgrade.bin"):
                        logging.info("move %s to %s", sysupgrade, self.path)

                        shutil.move(os.path.join(buildPath, sysupgrade), self.path)
                logging.info("build successfull")
            else:
                print(output.decode('utf-8'))
                logging.info("build failed")

    # check if image exists
    def created(self):
        # created images will be stored in downloads.lede-project.org like paths
        # the package should always be a sysupgrade
        logging.info("check path %s", self.path)
        return os.path.exists(self.path)

class ImageBuilder():
    def __init__(self, distro, version, target, subtarget):
        self.distro = distro
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.name = "-".join([self.distro, "imagebuilder", self.version, self.target, self.subtarget])
        self.name += ".Linux-x86_64"
        self.path = os.path.join("imagebuilder", self.distro, self.version, self.target, self.subtarget, self.name)
        if not os.path.exists(os.path.join(self.path, "Makefile")):
            logging.info("downloading imagebuilder %s", self.name)
            self.download()
        logging.info("initialized imagebuilder %s", self.name)

    def download(self): 
        ## tmp
        imagebuilder_url = "http://downloads.lede-project.org/releases/"

        ## /tmp
        create_folder(self.path)
        imagebuilder_url_path = os.path.join(self.version, "targets", self.target, self.subtarget, self.name)
        with tempfile.TemporaryDirectory() as tar_folder:
            logging.info("downloading %s", imagebuilder_url_path)
            tar_path = os.path.join(tar_folder, "imagebuilder.tar.xz")
            full_url = os.path.join(imagebuilder_url, imagebuilder_url_path)
            full_url += ".tar.xz"
            urllib.request.urlretrieve(full_url, tar_path)
            tar = tarfile.open(tar_path)
            tar.extractall(path=tar_folder)
            tar.close()
            shutil.move(os.path.join(tar_folder, self.name), self.path)

        
        #http://downloads.lede-project.org/releases/17.01.0/targets/ar71xx/generic/lede-imagebuilder-17.01.0-ar71xx-generic.Linux-x86_64.tar.xz


# todo move stuff to tmp and only move sysupgrade file
# usign für python ansehen
def create_folder(folder):
    try:
        if not os.path.exists(folder):
            if os.path.isfile(folder):
                folder = os.path.dirname(folder)

            os.makedirs(folder)
            logging.info("created folder %s", folder)
        return True
    except: 
        logging.error("could not create %s", folder)
        return False

if __name__ == "__main__":
    packages =  ["rpcd"]
    logging.info("started logger")
    image_ar71 = Image()
    image_ar71.request_variables("lede", "17.01.1", "ar71xx", "generic", "tl-wdr3600-v1", packages)
    image_x86 = Image()
    image_x86.request_variables("lede", "17.01.1", "x86", "64", "", packages)
    image_ar71.get()
    image_x86.get()
    imagebuilder_old = ImageBuilder("lede", "17.01.0", "ar71xx", "generic")

