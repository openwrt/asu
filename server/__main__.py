from flask import Flask
from flask import render_template
import logging

from utils.config import Config
from utils.common import usign_init
from utils.garbagecollector import GarbageCollector
from utils.boss import Boss
from utils.updater import Updater

app = Flask(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)
    log.info("start garbage collector")
    gaco = GarbageCollector()
    gaco.start()

    log.info("start boss")
    boss = Boss()
    boss.start()

    log.info("start updater")
    uper = Updater()
    uper.start()

    app.run()
