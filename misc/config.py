from pathlib import Path

# disable test and debug features
TESTING = False
DEBUG = False

# where to find the ImageBuildes
UPSTREAM_URL = "https://downloads.openwrt.org"

# where to store created images
STORE_PATH = Path.cwd() / "public/store/"

# where to store JSON files
JSON_PATH = Path.cwd() / "public/json/v1/"

MAPPING_ABI = {"libubus20191227": "libubus"}

# supported versions
BRANCHES = {
    "SNAPSHOT": {
        "name": "SNAPSHOT",
        "updates": "dev",
        "enabled": True,
        "snapshot": True,
        "versions": ["SNAPSHOT"],
        "git_branch": "master",
        "path": "snapshots",
        "path_packages": "snapshots/packages",
        "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
        "repos": ["base", "packages", "luci", "routing", "telephony"],
        "extra_repos": {},
        "extra_keys": [],
    },
    "21.02": {
        "name": "21.02",
        "updates": "features",
        "release_date": "2021-08-04",
        "enabled": True,
        "snapshot": False,
        "versions": [
            "21.02.0",
            "21.02-SNAPSHOT",
        ],
        "git_branch": "openwrt-21.02",
        "path": "releases/{version}",
        "path_packages": "releases/packages-{branch}",
        "pubkey": "RWQviwuY4IMGvwLfs6842A0m4EZU1IjczTxKMSk3BQP8DAQLHBwdQiaU",
        "repos": ["base", "packages", "luci", "routing", "telephony"],
        "extra_repos": {},
        "extra_keys": [],
    },
    "19.07": {
        "name": "19.07",
        "updates": "security",
        "release_date": "2021-08-07",
        "enabled": False,
        "versions": [
            "19.07.8",
            "19.07-SNAPSHOT",
        ],
        "git_branch": "openwrt-19.07",
        "path": "releases/{version}",
        "path_packages": "releases/packages-{branch}",
        "pubkey": "RWT5S53W/rrJY9BiIod3JF04AZ/eU1xDpVOb+rjZzAQBEcoETGx8BXEK",
        "repos": ["base", "packages", "luci", "routing", "telephony"],
        "extra_repos": {},
        "extra_keys": [],
    },
}
