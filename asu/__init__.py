from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from .common import cwd


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        STORE_PATH=Path(app.instance_path) / "store",
        TEST=False,
        DEBUG=True,
        UPSTREAM_URL="https://cdn.openwrt.org",
        VERSIONS={
            "SNAPSHOT": {
                "branch": "master",
                "path": "snapshots",
                "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
            }
        },
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    app.config["STORE_PATH"] = Path(app.config["STORE_PATH"])

    Path(app.instance_path).mkdir(exist_ok=True, parents=True)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.route("/")
    @app.route("/<path:path>")
    def root(path="index.html"):
        return send_from_directory(Path(app.instance_path) / "public", path)

    @app.route("/store/<path:path>")
    def send_js(path):
        return send_from_directory(cwd() / "store", path)

    from . import janitor

    app.register_blueprint(janitor.bp)

    from . import api

    app.register_blueprint(api.bp)

    return app
