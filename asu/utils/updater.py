import threading
from queue import Queue
import logging
import time

from asu.utils.config import Config
from asu.utils.database import Database
from asu.utils.worker import Worker

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class Updater(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.database = Database(self.config)
        self.update_queue = Queue(1)

    def run(self):
        location = self.config.get("updater_dir", "updater")
        Worker(location, None, None).setup_meta()
        workers = []

        # start all workers
        for i in range(0, self.config.get("updater_threads", 4)):
            log.info("starting updater thread {}".format(i))
            worker = Worker(location, "update", self.update_queue)
            worker.start()
            workers.append(worker)

        while True:
            outdated_target = self.database.get_outdated_target()
            if outdated_target:
                log.info("found outdated target %s", outdated_target)
                self.update_queue.put(outdated_target)
            else:
                time.sleep(5)
