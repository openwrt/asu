import logging
import hashlib
import os
import os.path
import subprocess

#logging.basicConfig(filename="output.log")
logging.basicConfig(level=logging.DEBUG)


class Image():
    def __init__(self, distro, version, target, subtarget, profile, packages):
        self.distro = distro
        self.version = version
        self.target = target
        self.subtarget = subtarget
        self.profile = profile
        self.packages = packages
        self.pkgHash = self.getPkgHash()
        self.name = self.profile + "-" + self.pkgHash +  ".img"
        self.name = "-".join([distro, version, self.pkgHash, target, subtarget, profile, "squashfs", "sysupgrade.bin"])
        self.path = os.path.join("download", self.distro, self.version, self.target, self.subtarget, self.name)
   
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
        ibPath = os.path.abspath(os.path.join("imagebuilder", self.target, self.subtarget))

        logging.info("use imagebuilder at %s", ibPath)

        buildPath = os.path.dirname(self.path)
        if not os.path.exists(buildPath):
            logging.info("create self path %s", self.path)
            os.makedirs(os.path.dirname(buildPath))

        cmdline = ["make", "image"]
        cmdline.append("PROFILE=%s" % self.profile)
        cmdline.append("PACKAGES='%s'" % " ".join(self.packages))
        cmdline.append("BIN_DIR=%s" % os.path.abspath(buildPath))
        cmdline.append("EXTRA_IMAGE_NAME=%s" % self.pkgHash)

        logging.info("start build: %s", cmdline)
        print(" ".join(cmdline))

        proc = subprocess.Popen(
            cmdline,
            cwd=ibPath,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )

        out, _ = proc.communicate()
        ret = proc.returncode
        print(ret)

    # check if image exists
    def created(self):
        # created images will be stored in downloads.lede-project.org like paths
        # ./lede/17.01.1/ar71xx/wr841-v1.5-6c7e907d06da.img
        # the package should always be a sysupgrade
        logging.info("check path %s", self.path)
        return os.path.exists(self.path)


if __name__ == "__main__":
    packages =  ["vim"]
    logging.info("started logger")
    image = Image("lede", "17.01.1", "ar71xx", "generic", "tl-wr841-v11", packages)
    print(image.get())
