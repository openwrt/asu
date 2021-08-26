import json
from os import getenv
from pathlib import Path

import connexion
from flask import Flask, redirect, send_from_directory
from redis import Redis

from asu import __version__


def create_app(test_config: dict = None) -> Flask:
    """Create the main Flask application

    Args:
        test_config (dict): A dictionry containing a configuration during tests

    Returns:
        Flask: The application
    """

    redis_host = getenv("REDIS_HOST", "localhost")
    redis_port = getenv("REDIS_PORT", 6379)
    redis_password = getenv("REDIS_PASSWORD", "")

    cnxn = connexion.FlaskApp(__name__)
    app = cnxn.app
    app.config.from_mapping(
        REDIS_CONN=Redis(host=redis_host, port=redis_port, password=redis_password),
        TESTING=False,
        DEBUG=False,
        UPSTREAM_URL="https://downloads.cdn.openwrt.org",
        BRANCHES={},
    )

    if not test_config:
        for config_file in [
            Path.cwd() / "config.py",
            "/etc/asu/config.py",
        ]:
            if Path(config_file).exists():
                print(f"Loading {config_file}")
                app.config.from_pyfile(config_file)
                break
    else:
        app.config.from_mapping(test_config)

    for option, value in app.config.items():
        if option.endswith("_PATH") and isinstance(value, (Path, str)):
            app.config[option] = Path(value)
            app.config[option].mkdir(parents=True, exist_ok=True)

    (Path().cwd()).mkdir(exist_ok=True, parents=True)

    @app.route("/json/")
    @app.route("/json/<path:path>")
    @app.route("/json/v1/<path:path>")
    def json_path(path="index.html"):
        return send_from_directory(app.config["JSON_PATH"], path)

    @app.route("/store/")
    @app.route("/store/<path:path>")
    def store_path(path="index.html"):
        return send_from_directory(app.config["STORE_PATH"], path)

    from . import janitor

    app.register_blueprint(janitor.bp)

    from . import api

    app.register_blueprint(api.bp)

    branches = dict(
        map(
            lambda b: (b["name"], b),
            filter(lambda b: b.get("enabled"), app.config["BRANCHES"].values()),
        )
    )
    latest = list(
        map(
            lambda b: b["versions"][0],
            filter(
                lambda b: b.get("enabled"),
                app.config["BRANCHES"].values(),
            ),
        )
    )

    app.config["OVERVIEW"] = {
        "latest": latest,
        "branches": branches,
        "server": {"version": __version__, "contact": "mail@aparcar.org"},
    }

    # legacy
    (app.config["JSON_PATH"] / "branches.json").write_text(json.dumps(branches))

    # tdb
    (app.config["JSON_PATH"] / "latest.json").write_text(json.dumps({"latest": latest}))

    (app.config["JSON_PATH"] / "overview.json").write_text(
        json.dumps(
            app.config["OVERVIEW"],
            indent=2,
        )
    )

    cnxn.add_api("openapi.yml", validate_responses=True)

    return app
