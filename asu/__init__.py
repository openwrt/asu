from pathlib import Path
from redis import Redis

from flask import Flask, redirect, send_from_directory
from flask_cors import CORS


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
        JSON_PATH=app.instance_path + "/public/json",
        CACHE_PATH=app.instance_path + "/cache/",
        REDIS_CONN=Redis(),
        TESTING=False,
        DEBUG=False,
        UPSTREAM_URL="https://downloads.cdn.openwrt.org",
        VERSIONS={},
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

    # only serve files in DEBUG/TESTING mode
    # production should use nginx for static files
    if app.config["DEBUG"] or app.config["TESTING"]:

        @app.route("/")
        @app.route("/<path:path>")
        def root(path="index.html"):
            return send_from_directory(Path(app.instance_path) / "public", path)

    else:

        @app.route("/")
        def root(path="index.html"):
            return redirect("https://github.com/aparcar/asu/#api")

    from . import janitor

    app.register_blueprint(janitor.bp)

    from . import api

    app.register_blueprint(api.bp)

    return app
