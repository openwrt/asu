from pathlib import Path

from flask import Flask, redirect, send_from_directory, g
from flask_cors import CORS
from rq_scheduler import Scheduler
from datetime import datetime


def create_app(test_config: dict = None) -> Flask:
    """Create the main Flask application

    Args:
        test_config (dict): A dictionry containing a configuration during tests

    Returns:
        Flask: The application
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        STORE_PATH=app.instance_path + "/public/store",
        JSON_PATH=app.instance_path + "/public/",
        CACHE_PATH=app.instance_path + "/cache/",
        REDIS_CONN="127.0.0.1",
        TESTING=False,
        DEBUG=False,
        UPSTREAM_URL="https://downloads.openwrt.org",
        UPSTREAM_SYNC_INTERVAL=60 * 60 * 6,  # every 6 hours
        VERSIONS={
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
                },
                {
                    "name": "19.07",
                    "enabled": False,
                    "eol": "2020-01-01",
                    "latest": "19.07.2",
                    "git_branch": "openwrt-19.07",
                    "pubkey": "RWT5S53W/rrJY9BiIod3JF04AZ/eU1xDpVOb+rjZzAQBEcoETGx8BXEK",
                    "release_date": "2020-01-31",
                    "updates": "bugs",
                },
                {
                    "name": "18.06",
                    "enabled": False,
                    "eol": "2019-01-01",
                    "latest": "18.06.7",
                    "git_branch": "openwrt-18.06",
                    "pubkey": "RWT5S53W/rrJY9BiIod3JF04AZ/eU1xDpVOb+rjZzAQBEcoETGx8BXEK",
                    "release_date": "2019-01-31",
                    "updates": "security",
                },
            ],
        },
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    for option, value in app.config.items():
        if option.endswith("_PATH") and isinstance(value, str):
            app.config[option] = Path(value)
            app.config[option].mkdir(parents=True, exist_ok=True)

    Path(app.instance_path).mkdir(exist_ok=True, parents=True)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.route("/")
    def root():
        return redirect("https://github.com/aparcar/asu/#api")

    if app.config["TESTING"]:
        from fakeredis import FakeRedis as Redis
    else:
        from redis import Redis

    app.redis = Redis(app.config["REDIS_CONN"])
    scheduler = Scheduler(connection=app.redis)

    from . import janitor

    # app.register_blueprint(janitor.bp)

    scheduler.schedule(
        scheduled_time=datetime.utcnow(),
        func=janitor.sync,
        args=[app.config],
        interval=app.config["UPSTREAM_SYNC_INTERVAL"],
    )

    from . import api

    app.register_blueprint(api.bp)

    return app
