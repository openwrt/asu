import threading
import signal
from socket import gethostname
import sys
import logging
import time
import os
from image import Image
from imagebuilder import ImageBuilder
import yaml
from config import Config
from database import Database

MAX_TARGETS=0

class Worker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        self.database = Database()
        self.log.info("database initialized")
        self.worker_id = None
        self.imagebuilders = []

    def worker_register(self):
        self.worker_id = str(self.database.worker_register(gethostname()))

    def worker_add_skill(self, imagebuilder):
        self.database.worker_add_skill(self.worker_id, *imagebuilder, 'ready')

    def add_imagebuilder(self):
        self.log.info("adding imagebuilder")
        imagebuilder_request = None

        while not imagebuilder_request:
            imagebuilder_request = self.database.worker_needed()
            if not imagebuilder_request:
                self.heartbeat()
                time.sleep(5)
                continue

            self.log.info("found worker_needed %s", imagebuilder_request)
            for imagebuilder_setup in self.imagebuilders:
                if len(set(imagebuilder_setup).intersection(imagebuilder_request)) == 4:
                    self.log.info("already handels imagebuilder")
                    return

            self.distro, self.release, self.target, self.subtarget = imagebuilder_request
            self.log.info("worker serves %s %s %s %s", self.distro, self.release, self.target, self.subtarget)
            imagebuilder = ImageBuilder(self.distro, str(self.release), self.target, self.subtarget)
            self.log.info("initializing imagebuilder")
            if imagebuilder.run():
                self.log.info("register imagebuilder")
                self.worker_add_skill(imagebuilder.as_array())
                self.imagebuilders.append(imagebuilder.as_array())
                self.log.info("imagebuilder initialzed")
            else:
                # manage failures
                # add in skill status
                pass
        self.log.info("added imagebuilder")

    def destroy(self, signal=None, frame=None):
        self.log.info("destroy worker %s", self.worker_id)
        self.database.worker_destroy(self.worker_id)
        sys.exit(0)

    def run(self):
        self.log.info("register worker")
        self.worker_register()
        while True:
            self.log.debug("severing %s", self.imagebuilders)
            build_job_request = None
            for imagebuilder in self.imagebuilders:
                build_job_request = self.database.get_build_job(*imagebuilder)
                if build_job_request:
                    break

            if build_job_request:
                self.log.debug("found build job")
                self.last_build_id = build_job_request[0]
                image = Image(*build_job_request[2:9])
                self.log.debug(image.as_array())
                if not image.run():
                    self.log.warn("build failed for %s", image.name)
                    self.database.set_build_job_fail(image.request_hash)
            else:
                # heartbeat should be more less than 5 seconds
                if len(self.imagebuilders) < MAX_TARGETS or MAX_TARGETS == 0:
                    self.add_imagebuilder()
                self.heartbeat()
                time.sleep(5)

    def heartbeat(self):
        self.log.debug("heartbeat %s", self.worker_id)
        self.database.worker_heartbeat(self.worker_id)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    #try:
    w = Worker()
#    signal.signal(signal.SIGINT, w.destroy)
    w.run()
    #finally:
    #    w.destroy()


