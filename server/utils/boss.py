import threading
from queue import Queue
import logging
import time

from utils.image import Image
from utils.common import get_hash
from utils.config import Config
from utils.database import Database
from utils.worker import Worker

class Boss(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger("boss")
        self.config = Config()
        self.database = Database(self.config)
        self.build_queue = Queue(1)

    def run(self):
        workers = []
        for worker_location in self.config.get("workers"):
            worker = Worker(worker_location, "image", self.build_queue)
            worker.start()
            workers.append(worker)

        while True:
            build_job = self.database.get_build_job()
            if build_job:
                self.log.info("found build job %s", build_job)
                self.build_queue.put(build_job)
            else:
                time.sleep(5)
