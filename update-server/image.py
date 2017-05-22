import logging
import subprocess

logging.basicConfig(filename="output.log")

class Image(distro, version, target, subtarget, model, profile, packages:
    distro = ""
    version = ""
    target = ""
    subtarget = ""
    profile = ""
    model = ""
    packages = []
    pkgHash = ""
    imageName = model + "-" + pkgHash +  ".img"
    imagePath = os.path.join(distro, version, target, subtarget, imgName)
   
    # returns the path of the created image
    def get():
        if not self.created():
            self.build() 

        return self.path


    # generate a hash of the installed packages
    def getPkgHash():
       pass 

    # builds the image with the specific packages at output path
    def build():
        # create image path
        ibPath = os.path.join("imagebuilder", image.target, image.subtarget)

        logging.info("use imagebuilder at %s", ibPath)

        if not os.path.exists(image.path):
            logging.info("create image path %s", image.path)
            os.makedirs(image.path)

        cmdline = ["make", "image"]
        cmdline.append("PROFILE=%s" % image.profile)
        cmdline.append("PACKAGES=%s" % image.packages)
        cmdline.append("BIN_DIR=%s" % image.path)

        logging.info("start build: %s", cmdline)

        proc = subprocess.Popen(
            cmdline,
            cwd=ibPath,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )

        out, _ = proc.communicate()
        ret = proc.returncode

    # check if image exists
    def created():
        # created images will be stored in downloads.lede-project.org like paths
        # ./lede/17.01.1/ar71xx/wr841-v1.5-6c7e907d06da.img
        # the package should always be a sysupgrade
        return os.path.exists(self.imagePath)
