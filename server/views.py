#!/usr/bin/env python3

from flask import Flask
from flask import render_template, request, send_from_directory
import json
import os
from http import HTTPStatus

from server.build_request import BuildRequest
from server.upgrade_check import UpgradeCheck
from server import app

from utils.config import Config
from utils.database import Database

config = Config()
database = Database(config)

uc = UpgradeCheck(config, database)
br = BuildRequest(config, database)

@app.route("/update-request", methods=['POST'])
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

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def download_image(image_path, image_name):
    return send_from_directory(directory=os.path.join(config.get_folder("download_folder"), image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/image-request", methods=['POST']) # legacy
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

@app.route("/build-request", methods=['POST']) # legacy
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

@app.route("/")
def root_path():
    return render_template("index.html")

@app.route("/stats")
def stats():
    return render_template("stats.html",
            popular_subtargets=database.get_popular_subtargets(),
            images_count=database.get_images_count(),
            images_total=database.get_images_total(),
            packages_count=database.get_packages_count())

@app.route("/api/distros")
def api_distros():
    return app.response_class(
            response=database.get_supported_distros(),
            mimetype='application/json')

@app.route("/api/versions")
def api_versions():
    distro = request.args.get("distro", "")
    return app.response_class(
            response=database.get_supported_versions(distro),
            mimetype='application/json')

@app.route("/api/models")
def api_models():
    distro = request.args.get("distro", "")
    version = request.args.get("version", "")
    model_search = request.args.get("model_search", "")
    if distro != "" and version != "" and model_search != "":
        return app.response_class(
                response=database.get_supported_models(model_search, distro, version),
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/packages_image")
@app.route("/api/default_packages")
def api_default_packages():
    distro = request.args.get("distro", "")
    version = request.args.get("version", "")
    target = request.args.get("target", "")
    subtarget = request.args.get("subtarget", "")
    profile = request.args.get("profile", "")
    if distro != "" and version != "" and target != "" and subtarget != "" and profile != "":
        return app.response_class(
                response=database.get_image_packages(distro, version, target, subtarget, profile),
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/image/<image_hash>")
def api_image(image_hash):
    return app.response_class(
            response=database.get_image_info(image_hash),
            mimetype='application/json')

@app.route("/api/manifest/<manifest_hash>")
def api_manifest(manifest_hash):
    return app.response_class(
            response=database.get_manifest_info(manifest_hash),
            mimetype='application/json')

@app.route("/supported")
def supported():
    show_json = request.args.get('json', False)
    if show_json:
        distro = request.args.get('distro', '%')
        version = request.args.get('version', '%')
        target = request.args.get('target', '%')
        supported = database.get_subtargets_json(distro, version, target)
        return supported
    else:
        supported = database.get_subtargets_supported()
        return render_template("supported.html", supported=supported)
