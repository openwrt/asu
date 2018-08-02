from worker import Worker
from utils.database import Database
from utils.config import Config

conf = Config()

db = Database(conf)
print("Outdated subtarget", db.get_subtarget_outdated())

#params = { "distro": "openwrt", "version": "18.06.0-rc2", "target": "ar71xx", "subtarget": "generic" }
#Worker("info", "/tmp/worker", params).run()


params = { "worker": "/tmp/worker", "distro": "openwrt", "version": "18.06.0-rc2", "target": "ar71xx", "subtarget": "generic", "profile": "tl-wdr4300-v1" }
Worker("image", params).run()
