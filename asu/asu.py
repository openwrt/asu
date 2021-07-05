from pathlib import Path
from redis import Redis

from flask import Flask, redirect, send_from_directory
from flask_cors import CORS

import json
from os import getenv


def create_app(test_config: dict = None) -> Flask:
    """Create the main Flask application

    Args:
        test_config (dict): A dictionry containing a configuration during tests

    Returns:
        Flask: The application
    """

    redis_host = getenv("REDIS_HOST", "localhost")
    redis_port = getenv("REDIS_PORT", 6379)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        STORE_PATH=app.instance_path + "/public/store",
        JSON_PATH=app.instance_path + "/public/json",
        CACHE_PATH=app.instance_path + "/cache/",
        REDIS_CONN=Redis(host=redis_host, port=redis_port),
        TESTING=False,
        DEBUG=False,
        UPSTREAM_URL="https://downloads.cdn.openwrt.org",
        BRANCHES={},
    )

    if not test_config:
        for config_file in [
            Path.cwd() / "config.py",
            app.instance_path + "/config.py",
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

    Path(app.instance_path).mkdir(exist_ok=True, parents=True)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # only serve files in DEBUG/TESTING mode
    # production should use nginx for static files
    if app.config["DEBUG"] or app.config["TESTING"]:

        @app.route("/")
        @app.route("/<path:path>")
        def root(path="index.html"):
            return send_from_directory(Path(app.instance_path) / "public", path)

        @app.route("/store/")
        @app.route("/store/<path:path>")
        def store(path="index.html"):
            return send_from_directory(app.config["STORE_PATH"], path)

    else:

        @app.route("/")
        def root(path="index.html"):
            return redirect("https://github.com/aparcar/asu/#api")

    from . import janitor

    app.register_blueprint(janitor.bp)

    from . import api

    app.register_blueprint(api.bp)

    (app.config["JSON_PATH"] / "branches.json").write_text(
        json.dumps(app.config["BRANCHES"])
    )

    return app
