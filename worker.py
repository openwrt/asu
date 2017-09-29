#!/usr/bin/env python3
import signal
import logging

from worker.worker import Worker

logging.basicConfig(level=logging.DEBUG)
w = Worker()
signal.signal(signal.SIGINT, w.destroy)
signal.signal(signal.SIGTERM, w.destroy)
w.run()
