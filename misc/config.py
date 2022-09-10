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

MAPPING_ABI = {"libubus20191227": "libubus"}
