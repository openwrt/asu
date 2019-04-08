import threading
import shutil
import os
import os.path
import logging
import time

from asu.utils.config import Config
from asu.utils.database import Database


class GarbageCollector(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.config = Config()
        self.database = Database(self.config)

    def del_image(self, image):
        image_hash, image_path = image
        self.log.debug("remove outdated image %s", image)
        self.database.del_image(image_hash)
        if os.path.exists(image_path):
            shutil.rmtree(image_path)

    def run(self):
        while True:
            # remove outdated snapshot builds
            for outdated_snapshot in self.database.get_outdated_snapshots():
                self.del_image(outdated_snapshot)

            # del custom images older than 7 days
            for outdated_custom in self.database.get_outdated_customs():
                self.del_image(outdated_custom)

            # TODO reimplement
            # del oudated manifests
            for outdated_manifest in self.database.get_outdated_manifests():
                self.del_image(outdated_manifest)

            # del outdated snapshot requests
            self.database.del_outdated_request()

            # run every 6 hours
            time.sleep(3600 * 6)
