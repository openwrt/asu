import logging
from datetime import timedelta

import requests
from flask import Blueprint
from rq import Queue

from asu.common import (
    get_redis_client,
    update_meta_json,
    update_profiles,
    update_targets,
)

bp = Blueprint("janitor", __name__)

session = requests.Session()


def update_branch(config, branch):
    logging.debug(f"Update {branch['name']}")

    targets = list(update_targets(config, branch["versions"][0]).keys())

    logging.debug(f"Targets: {targets}")

    if not targets:
        logging.warning(f"No targets found for {branch['name']}")
        return

    for version in branch["versions"]:
        logging.info(f"Update {branch['name']}/{version}")

        for target in targets:
            logging.info(f"Update {branch['name']}/{version}/{target}")
            update_profiles(config, version, target)


def update_branches(config):
    """Update the data required to run the server

    For this all available profiles for all enabled versions is
    downloaded and stored in the Redis database.
    """

    if not config["BRANCHES"]:
        logging.error("No BRANCHES defined in config, nothing to do, exiting")
        return

    try:
        for branch in config["BRANCHES"].values():
            if not branch.get("enabled"):
                logging.info(f"{branch['name']}: Skip disabled branch")
                continue

            logging.info(f"Update {branch['name']}")
            update_branch(config, branch)

        update_meta_json(config)
    except Exception as e:
        logging.exception(e)

    Queue(connection=get_redis_client(config)).enqueue_in(
        timedelta(hours=1),
        update_branches,
        config,
        job_timeout="15m",
    )
