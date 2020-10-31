# where to store created images
# STORE_PATH="/var/asu/public/store",

# disable test and debug features
TESTING = False
DEBUG = False

# where to find the ImageBuildes
UPSTREAM_URL = "https://downloads.cdn.openwrt.org"

# Workaround until upstream actually creates JSON files
JSON_URL = "https://images.aparcar.org/rebuild/"

# supported versions
VERSIONS = {
    "metadata_version": 1,
    "branches": [
        {
            "name": "snapshot",
            "enabled": True,
            "latest": "snapshot",
            "git_branch": "master",
            "path": "snapshots",
            "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
            "updates": "dev",
            "extra_repos": {
                "lime-packages": "https://feed.libremesh.org/master",
                "lime-profiles": "https://feed.libremesh.org/profiles",
            },
        },
        {
            "name": "19.07",
            "enabled": False,
            "eol": "2020-01-01",
            "latest": "19.07.3",
            "git_branch": "openwrt-19.07",
            "path": "releases/19.07.3",
            "pubkey": "RWT5S53W/rrJY9BiIod3JF04AZ/eU1xDpVOb+rjZzAQBEcoETGx8BXEK",
            "release_date": "2020-01-31",
            "updates": "bugs",
            "extra_repos": {
                "lime-packages": "https://feed.libremesh.org/master",
                "lime-profiles": "https://feed.libremesh.org/profiles",
            },
        },
        {
            "name": "18.06",
            "enabled": False,
            "eol": "2019-01-01",
            "latest": "18.06.7",
            "git_branch": "openwrt-18.06",
            "path": "releases/18.06.7",
            "pubkey": "RWT5S53W/rrJY9BiIod3JF04AZ/eU1xDpVOb+rjZzAQBEcoETGx8BXEK",
            "release_date": "2019-01-31",
            "updates": "security",
        },
    ],
}
