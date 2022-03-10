import json

# from msilib.schema import Registry
from os import getenv
from pathlib import Path

import connexion
from flask import Flask, render_template, send_from_directory
from prometheus_client import CollectorRegistry, make_wsgi_app
from redis import Redis
from werkzeug.middleware.dispatcher import DispatcherMiddleware

import asu.common
from asu import __version__


def create_app(test_config: dict = None) -> Flask:
    """Create the main Flask application

    Args:
        test_config (dict): A dictionary containing a configuration during tests

    Returns:
        Flask: The application
    """

    redis_host = getenv("REDIS_HOST", "localhost")
    redis_port = getenv("REDIS_PORT", 6379)
    redis_password = getenv("REDIS_PASSWORD", "")

    cnxn = connexion.FlaskApp(__name__)
    app = cnxn.app

    app.config.from_mapping(
        JSON_PATH=Path.cwd() / "public/json/v1/",
        REDIS_CONN=Redis(host=redis_host, port=redis_port, password=redis_password),
        TESTING=False,
        DEBUG=False,
        UPSTREAM_URL="https://downloads.openwrt.org",
        BRANCHES={},
        ALLOW_DEFAULTS=False,
        ASYNC_QUEUE=True,
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
        app.config["REGISTRY"] = CollectorRegistry()
    else:
        app.config.from_mapping(test_config)

    for option, value in app.config.items():
        if option.endswith("_PATH") and isinstance(value, (Path, str)):
            app.config[option] = Path(value)
            app.config[option].mkdir(parents=True, exist_ok=True)

    app.wsgi_app = DispatcherMiddleware(
        app.wsgi_app, {"/metrics": make_wsgi_app(app.config["REGISTRY"])}
    )

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

    from . import metrics

    app.config["REGISTRY"].register(metrics.BuildCollector(app.config["REDIS_CONN"]))

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
        "server": {
            "version": __version__,
            "contact": "mail@aparcar.org",
            "allow_defaults": app.config["ALLOW_DEFAULTS"],
        },
    }

    # legacy
    (app.config["JSON_PATH"] / "branches.json").write_text(
        json.dumps(list(branches.values()))
    )

    # tdb
    (app.config["JSON_PATH"] / "latest.json").write_text(json.dumps({"latest": latest}))

    (app.config["JSON_PATH"] / "overview.json").write_text(
        json.dumps(
            app.config["OVERVIEW"],
            indent=2,
        )
    )

    @app.route("/")
    def overview():
        return render_template(
            "overview.html",
            branches=branches,
            defaults=app.config["ALLOW_DEFAULTS"],
            latest=latest,
            version=__version__,
        )

    @app.route("/stats")
    def stats():
        branch_stats = {}
        for branch, data in branches.items():
            branch_stats.setdefault(branch, {})["profiles"] = asu.common.stats_profiles(
                branch
            )[0:5]
        return render_template(
            "stats.html",
            versions=asu.common.stats_versions(),
            branch_stats=branch_stats,
        )

    for package, source in app.config.get("MAPPING_ABI", {}).items():
        if not app.config["REDIS_CONN"].hexists("mapping-abi", package):
            app.config["REDIS_CONN"].hset("mapping-abi", package, source)

    cnxn.add_api("openapi.yml", validate_responses=app.config["TESTING"])

    return app
