from asu import app

from flask import request, send_from_directory, redirect, jsonify
import json
import click
import logging
import os
from http import HTTPStatus
import urllib.request

from asu.build_request import BuildRequest
from asu.upgrade_check import UpgradeCheck
from asu.utils.config import Config
from asu.utils.common import get_hash, get_packages_hash, get_request_hash
from asu.utils.database import Database

log = logging.getLogger(__name__)
config = Config()
database = Database(config)

uc = UpgradeCheck(config, database)
br = BuildRequest(config, database)

@app.route("/api/upgrade-check", methods=['POST'])
@app.route("/api/upgrade-check/<request_hash>", methods=['GET'])
def api_upgrade_check(request_hash=None):
    if request.method == 'POST':
        try:
            request_json = json.loads(request.get_data().decode('utf-8'))
        except:
            return "[]", HTTPStatus.BAD_REQUEST
    else:
        if not request_hash:
            return "[]", HTTPStatus.BAD_REQUEST
        request_json = { "request_hash": request_hash }
    return uc.process_request(request_json)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/api/upgrade-request", methods=['POST'])
@app.route("/api/upgrade-request/<request_hash>", methods=['GET'])
def api_upgrade_request(request_hash=None):
    if request.method == 'POST':
        try:
            request_json = json.loads(request.get_data().decode('utf-8'))
        except:
            return "[]", HTTPStatus.BAD_REQUEST
    else:
        if not request_hash:
            return "[]", HTTPStatus.BAD_REQUEST
        request_json = { "request_hash": request_hash }

    return br.process_request(request_json, sysupgrade_requested=1)

@app.route("/")
@app.route("/api/")
@app.route("/stats/")
def api_redirect():
    return redirect("https://github.com/aparcar/attendedsysupgrade-server/")

@app.route("/api/build-request", methods=['POST'])
@app.route("/api/build-request/<request_hash>", methods=['GET'])
def api_files_request(request_hash=None):
    if request.method == 'POST':
        try:
            request_json = json.loads(request.get_data().decode('utf-8'))
        except:
            return "[]", HTTPStatus.BAD_REQUEST
    else:
        if not request_hash:
            return "[]", HTTPStatus.BAD_REQUEST
        request_json = { "request_hash": request_hash }
    return br.process_request(request_json)

@app.route("/api/v1/stats/image_stats")
def api_stats_image_stats():
    return mime_json(database.get_image_stats())

@app.route("/api/v1/stats/images_latest")
def api_stats_images_latest():
    return mime_json(database.get_images_latest())

@app.route("/api/v1/stats/fails_latest")
def api_stats_fails_latest():
    return mime_json(database.get_fails_latest())

# create response with mimetype set to json
# usefull when json is directly created by postgresql
def mime_json(response):
    return app.response_class(
            response=response,
            mimetype='application/json')

@app.route("/api/v1/stats/popular_targets")
def api_stats_popular_targets():
    return mime_json(database.get_popular_targets())

@app.route("/api/v1/stats/popular_packages")
def api_stats_popular_packages():
    return mime_json(database.get_popular_packages())

@app.route("/api/distros")
def api_distros():
    return mime_json(database.api_get_distros())

@app.route("/api/distributions")
def api_distributions():
    return mime_json(config.get_all())

@app.route("/api/versions")
def api_versions():
    return mime_json(database.api_get_versions())

@app.route("/api/models")
def api_models():
    distro = request.args.get("distro", "")
    version = request.args.get("version", "")
    model_search = request.args.get("model_search", "")
    if distro != "" and version != "":
        return mime_json(database.get_supported_models_json(model_search, distro, version))
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/packages_image")
def api_default_packages():
    distro = request.args.get("distro", "")
    version = request.args.get("version", "")
    target = request.args.get("target", "")
    profile = request.args.get("profile", "")
    if distro and version and target and profile:
        return jsonify(database.get_packages_image({
            "distro": distro,
            "version": version,
            "target": target,
            "profile": profile}))
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/image/<image_hash>")
def api_image(image_hash):
    return mime_json(database.get_image_info(image_hash))

@app.route("/api/v1/packages_hash/<packages_hash>")
def api_packages_hash(packages_hash):
    return mime_json(database.get_packages_hash(packages_hash))

@app.route("/api/manifest/<manifest_hash>")
def api_manifest(manifest_hash):
    return mime_json(database.get_manifest_info(manifest_hash))

@app.route("/api/v1/supported")
def api_supported():
    return mime_json(database.get_supported_targets_json())

@app.cli.command()
def load_database():
    fetch_targets()
    load_tables()
    insert_board_rename()

@app.cli.command()
def fetch_targets():
    for distro in config.get("active_distros", ["openwrt"]):
        # set distro alias like OpenWrt, fallback would be openwrt
        database.insert_dict("distros", {
            "distro": distro,
            "distro_alias": config.get(distro).get("distro_alias", distro),
            "distro_description": config.get(distro).get("distro_description", ""),
            "latest": config.get(distro).get("latest")
            })
        for version in config.get(distro).get("versions", []):
            version_config = config.version(distro, version)
            database.insert_dict("versions", {
                "distro": distro,
                "version": version,
                "version_alias": version_config.get("version_alias", version),
                "version_description": version_config.get("version_description", ""),
                "snapshots": version_config.get("snapshots", False)
                })
            version_config = config.version(distro, version)
            version_url = version_config.get("targets_url")
            # use parent_version for ImageBuilder if exists
            version_imagebuilder = version_config.get("parent_version", version)

            version_targets = set(json.loads(urllib.request.urlopen(
                "{}/{}/targets?json-targets".format(version_url,
                    version_imagebuilder)).read().decode('utf-8')))

            if version_config.get("active_targets"):
                version_targets = version_targets & set(version_config.get("active_targets"))

            if version_config.get("ignore_targets"):
                version_targets = version_targets - set(version_config.get("ignore_targets"))

            log.info("add %s/%s targets", distro, version)
            database.insert_target(distro, version, version_targets)

@app.cli.command()
def build_all():
    for profile in database.get_all_profiles(
            "openwrt", config.get("openwrt").get("latest")):
        target, profile = profile
        params = {
            "distro": "openwrt",
            "version": config.get("openwrt").get("latest"),
            "target": target,
            "profile": profile
            }
        database.insert_dict("requests", params)

@app.cli.command()
def build_worker():
    log.info("build worker image")
    packages = ["bash", "bzip2", "coreutils", "coreutils-stat", "diffutils",
            "file", "gawk", "gcc", "getopt", "git", "libncurses", "make",
            "patch", "perl", "perlbase-attributes", "perlbase-findbin",
            "perlbase-getopt", "perlbase-thread", "python-light", "tar",
            "unzip", "wget", "xz", "xzdiff", "xzgrep", "xzless", "xz-utils",
            "zlib-dev"]

    packages_hash = get_packages_hash(packages)
    database.insert_packages_hash(packages_hash, packages)

    params = {
        "distro": "openwrt",
        "version": config.get("openwrt").get("latest"),
        "target": "x86/64",
        "profile": "Generic",
        "packages_hash": packages_hash
        }

    params["request_hash"] = get_request_hash(params)

    database.insert_dict("requests", params)

def insert_board_rename():
    for distro, version in database.get_versions():
        version_config = config.version(distro, version)
        if "board_rename" in version_config:
            for origname, newname in version_config["board_rename"].items():
                log.info("insert board_rename {} {} {} {}".format(distro, version, origname, newname))
                database.insert_board_rename(distro, version, origname, newname)

def insert_transformations(distro, version, transformations):
    for package, action in transformations.items():
        if not action:
            # drop package
            #print("drop", package)
            database.insert_transformation(distro, version, package, None, None)
        elif isinstance(action, str):
            # replace package
            #print("replace", package, "with", action)
            database.insert_transformation(distro, version, package, action, None)
        elif isinstance(action, dict):
            for choice, context in action.items():
                if context is True:
                    # set default
                    #print("default", choice)
                    database.insert_transformation(distro, version, package, choice, None)
                elif context is False:
                    # possible choice
                    #print("choice", choice)
                    # TODO
                    pass
                elif isinstance(context, list):
                    for dependencie in context:
                        # if context package exists
                        #print("dependencie", dependencie, "for", choice)
                        database.insert_transformation(distro, version, package, choice, dependencie)

def load_tables():
    for distro, version in database.get_versions():
        log.debug("load tables %s %s", distro, version)
        version_transformations_path = os.path.join("distributions", distro, (version + ".yml"))
        if os.path.exists(version_transformations_path):
            with open(version_transformations_path, "r") as version_transformations_file:
                transformations = yaml.load(version_transformations_file.read())
                if transformations:
                    if "transformations" in transformations:
                        insert_transformations(distro, version, transformations["transformations"])

