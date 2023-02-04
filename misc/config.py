from pathlib import Path

# disable test and debug features
TESTING = False
DEBUG = False

# where to find the ImageBuildes
UPSTREAM_URL = "https://downloads.openwrt.org"

# where to store created images
STORE_PATH = Path.cwd() / "public/store/"

# where to store ImageBuilders. Do not set when multiple workers run
CACHE_PATH = None

# where to store JSON files
JSON_PATH = Path.cwd() / "public/json/v1/"

# manual mapping of package ABI changes
MAPPING_ABI = {"libubus20191227": "libubus"}

# connection string for Redis
# REDIS_CONN = Redis(host=redis_host, port=redis_port, password=redis_password)

# run jobs in worker processes or on the server (for testing)
# ASYNC_QUEUE = True

# allow users to add a boot script to the images
# ALLOW_DEFAULTS = False

# definition of branches, see and use branches.yml instead (unless testing)
# BRANCHES = {}

# what branches.yml file to load
# BRANCHES_FILE = "./branches.yml"

# where to downlaod the images from
# UPSTREAM_PATH = "https://downloads.openwrt.org"
