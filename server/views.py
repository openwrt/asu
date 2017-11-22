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
from utils.common import get_dir, create_folder, init_usign

database = Database()
config = Config()


@app.route("/update-request", methods=['POST'])
@app.route("/api/upgrade-check", methods=['POST'])
def api_upgrade_check():
    try:
        request_json = json.loads(request.get_data().decode('utf-8'))
    except:
        return "[]", HTTPStatus.BAD_REQUEST
    ur = UpdateRequest(request_json)
    return(ur.run())

# direct link to download a specific image based on hash
@app.route("/download/<path:image_path>/<path:image_name>")
def download_image(image_path, image_name):
    return send_from_directory(directory=os.path.join(get_dir("downloaddir"), image_path), filename=image_name)

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/image-request", methods=['POST'])
@app.route("/api/upgrade-request", methods=['POST', 'GET'])
@app.route("/api/upgrade-request/<request_hash>", methods=['GET'])
def api_upgrade_request(request_hash=""):
    if request.method == 'POST':
        try:
            request_json = json.loads(request.get_data().decode('utf-8'))
            ir = ImageRequest(request_json, 1)
        except:
            return "[]", HTTPStatus.BAD_REQUEST
    else:
        if not request_hash:
            return "[]", HTTPStatus.BAD_REQUEST
        ir = ImageRequest({ "request_hash": request_hash }, 1)
    return(ir.get_image(sysupgrade=1))

@app.route("/build-request", methods=['POST'])
@app.route("/api/build-request", methods=['POST'])
@app.route("/api/build-request/<request_hash>", methods=['GET'])
def api_files_request(request_hash=""):
    if request.method == 'POST':
        try:
            request_json = json.loads(request.get_data().decode('utf-8'))
            ir = ImageRequest(request_json)
        except:
            return "[]", HTTPStatus.BAD_REQUEST
    else:
        if not request_hash:
            return "[]", HTTPStatus.BAD_REQUEST
        ir = ImageRequest({ "request_hash": request_hash })
    return(ir.get_image(sysupgrade=1))

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
            status=HTTPStatus.OK,
            mimetype='application/json')

@app.route("/api/releases")
def api_releases():
    distro = request.args.get("distro", "")
    return app.response_class(
            response=database.get_supported_releases(distro),
            status=HTTPStatus.OK,
            mimetype='application/json')

@app.route("/api/models")
def api_models():
    distro = request.args.get("distro", "")
    release = request.args.get("release", "")
    model_search = request.args.get("model_search", "")
    if distro != "" and release != "" and model_search != "":
        return app.response_class(
                response=database.get_supported_models(model_search, distro, release),
                status=HTTPStatus.OK,
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/api/network_profiles")
def api_network_profiles():
    return app.response_class(
            response=utils.common.get_network_profiles(),
            status=HTTPStatus.OK,
            mimetype='application/json')

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
                status=HTTPStatus.OK,
                mimetype='application/json')
    else:
        return "[]", HTTPStatus.BAD_REQUEST

@app.route("/imagebuilder")
def imagebuilder():
    return render_template("chef.html", update_server=config.get("update_server"))

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
