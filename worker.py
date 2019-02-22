from asu.utils.garbagecollector import GarbageCollector
from asu.utils.boss import Boss
from asu.utils.updater import Updater

import logging

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
