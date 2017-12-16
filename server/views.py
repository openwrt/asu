#!/usr/bin/env python3

from flask import Flask
from flask import render_template, request, send_from_directory, redirect, jsonify
import json
import socket
import os
import logging
from http import HTTPStatus

from server.update_request import UpdateRequest
from server.image_request import ImageRequest
from server import app

import utils
from utils.config import Config
from utils.database import Database
from utils.common import get_folder, create_folder, init_usign

config = Config()
database = Database(config)

ur = UpdateRequest(config, database)
ir = ImageRequest(config, database)

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
    return ur.request(request_json)

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def download_image(image_path, image_name):
    return send_from_directory(directory=os.path.join(get_folder("downloaddir"), image_path), filename=image_name)

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

    return ir.request(request_json, sysupgrade=1)

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
    return ir.request(request_json)

@app.route("/")
def root_path():
    return render_template("index.html",
            popular_subtargets=database.get_popular_subtargets(),
            worker_active=database.get_worker_active(),
            images_count=database.get_images_count(),
            images_total=database.get_images_total(),
            packages_count=database.get_packages_count())

@app.route("/api/distros")
def api_distros():
    return app.response_class(
            response=database.get_supported_distros(),
            mimetype='application/json')

@app.route("/api/releases")
def api_releases():
    distro = request.args.get("distro", "")
    return app.response_class(
            response=database.get_supported_releases(distro),
            mimetype='application/json')

@app.route("/api/models")
def api_models():
    distro = request.args.get("distro", "")
    release = request.args.get("release", "")
    model_search = request.args.get("model_search", "")
    if distro != "" and release != "" and model_search != "":
        return app.response_class(
                response=database.get_supported_models(model_search, distro, release),
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/packages_image")
def api_packages_image():
    data = []
    distro = request.args.get("distro", "")
    release = request.args.get("release", "")
    target = request.args.get("target", "")
    subtarget = request.args.get("subtarget", "")
    profile = request.args.get("profile", "")
    if distro != "" and release != "" and target != "" and subtarget != "" and profile != "":
        return app.response_class(
                response=database.get_image_packages(distro, release, target, subtarget, profile, as_json=True),
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/image/<image_hash>")
def api_image(image_hash):
    return app.response_class(
            response=database.get_image_info(image_hash, json=True) ,
            mimetype='application/json')

@app.route("/api/manifest/<manifest_hash>")
def api_manifest(manifest_hash):
    return app.response_class(
            response=database.get_manifest_info(manifest_hash, json=True),
            mimetype='application/json')

@app.route("/supported")
def supported():
    show_json = request.args.get('json', False)
    if show_json:
        distro = request.args.get('distro', '%')
        release = request.args.get('release', '%')
        target = request.args.get('target', '%')
        supported = database.get_subtargets_json(distro, release, target)
        return supported
    else:
        supported = database.get_subtargets_supported()
        return render_template("supported.html", supported=supported)

@app.route("/image/<image_hash>")
def image(image_hash):
    image = database.get_image_info(image_hash)
    manifest = database.get_manifest_info(image["manifest_hash"])
    return render_template("image.html", **image, manifest=manifest)

@app.route("/fails")
def fails():
    fails = database.get_fails_list()
    return render_template("fails.html", fails=fails)

@app.route("/packages-hash/<packages_hash>")
def packages_hash(packages_hash):
    packages = database.get_packages_hash(packages_hash).split(" ")
    return render_template("packages_list.html", packages=packages)

@app.route("/manifest-info/<manifest_hash>")
def image_info(manifest_hash):
    manifest = database.get_manifest_info(manifest_hash)
    return render_template("manifest-info.html", manifest=manifest)

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/worker/register", methods=['POST'])
def worker_register():
    request_json = request.json
    print(request_json)
    return str(database.worker_register(
        request_json["worker_name"],
        request_json["worker_address"],
        request_json["worker_pubkey"]))

@app.route("/worker/add_skill", methods=['POST'])
def worker_add_skill():
    request_json = request.json
    return app.response_class(response=database.worker_add_skill(
        request_json["worker_id"],
        request_json["distro"],
        request_json["release"],
        request_json["target"],
        request_json["subtarget"],
        request_json["status"]),
        mimetype='application/json')

@app.route("/worker/needed", methods=['POST'])
def worker_needed():
    return app.response_class(response=database.worker_needed(worker=True), 
        mimetype='application/json')

@app.route("/worker/destroy", methods=['POST'])
def worker_destroy():
    request_json = request.json
    return database.worker_destroy(request_json["worker_id"])

@app.route("/worker/add_manifest", methods=['POST'])
def worker_add_manifest():
    rj = request.json
    database.add_manifest_packages(rj["manifest_hash"], rj["manifest_packages"])
    return "", 200

@app.route("/worker/build_job", methods=['POST'])
def worker_build_job():
    request_json = request.json
    result = database.get_build_job(
        request_json["distro"],
        request_json["release"],
        request_json["target"],
        request_json["subtarget"])
    print(result)
    return jsonify(result)

@app.route("/worker/hearbeat", methods=['POST'])
def worker_heartbeat():
    request_json = request.json
    database.worker_heartbeat(request_json["worker_id"])
    return "", 200

@app.route("/worker/build_done", methods=['POST'])
def worker_build_done():
    request_json = request.json
    database.worker_done_build(request_json["request_hash"], request_json["image_hash"], request_json["build_status"])
    return "", 200

@app.route("/worker/request_status", methods=['POST'])
def worker_request_status():
    request_json = request.json
    database.set_image_requests_status(request_json["request_hash"], request_json["status"])
    return "", 200

@app.route("/worker/add_image", methods=['POST'])
def worker_add_image():
    request_json = request.json
    database.add_image(
        request_json["image_hash"],
        request_json["distro"],
        request_json["release"],
        request_json["target"],
        request_json["subtarget"],
        request_json["profile"],
        request_json["manifest_hash"],
        request_json["sysupgrade_suffix"],
        request_json["subtarget_in_name"],
        request_json["profile_in_name"],
        request_json["vanilla"],
        request_json["build_seconds"])
    return "", 200
