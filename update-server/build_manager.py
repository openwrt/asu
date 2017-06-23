import socket
from image import Image
import threading
import logging
import time
from database import Database
from config import Config
import os

class BuildManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.log = logging.getLogger(__name__)
        self.database = Database()
        self.last_build_id = 1

    def get_last_build_id(self):
        print("foobar", self.last_build_id)
        return self.last_build_id

    def run(self):
        while True:
            build_job_request = self.database.get_build_job()
            print(build_job_request)
            if not build_job_request:
                self.log.debug("build queue is empty")
                time.sleep(5)
            else:
                self.last_build_id = build_job_request[0]
                image = Image(*build_job_request[2:8])
                if not image.created():
                    if image.run():
                        self.database.del_build_job(build_job_request[1])
                    else:
                        self.database.set_build_job_fail(build_job_request[1])
                        self.log.warn("build failed for %s", image.name)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bm = BuildManager()
    bm.start()

    socket_name = "/tmp/build_manager_last_build_id"
    if os.path.exists(socket_name):
        os.remove(socket_name)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_name)
    server.listen()

    while True:
        print("wait for connection - last_build_id: {}".format(bm.get_last_build_id()))
        connection, client_address = server.accept()
        try:
            connection.send(str(bm.get_last_build_id()).encode())
        finally:
            connection.close()
