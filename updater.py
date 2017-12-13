import threading
import signal
import logging
import time

from worker.imagebuilder import ImageBuilder
from utils.config import Config
from utils.database import Database

class Updater(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.db = Database(config)
        self.log.info("db initialized")

    def run(self):
        self.log.info("run updater")
        while True:
            outdated_subtarget = self.db.get_subtarget_outdated()

            if not outdated_subtarget:
                self.log.debug("updater sleeping")
                time.sleep(60)
            else:
                self.log.info("found outdated_subtarget %s", outdated_subtarget)
                distro, release, target, subtarget = outdated_subtarget
                imagebuilder = ImageBuilder(distro, str(release), target, subtarget)
                self.log.info("initializing imagebuilder")
                if not imagebuilder.created():
                    self.log.info("setup imagebuilder")
                    imagebuilder.run()
                    self.log.info("parse profiles/default packages")
                    info = imagebuilder.parse_info()
                    if info:
                        self.db.insert_profiles(distro, release, target, subtarget, *info)
                    else:
                        logging.error("could not receive profiles of %s/%s", target, subtarget)
                        exit(1)

                self.log.info("parse packages")
                packages = imagebuilder.parse_packages()
                self.db.insert_packages_available(distro, release, target, subtarget, packages)
                self.db.subtarget_synced(distro, release, target, subtarget)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    u = Updater()
    u.run()
