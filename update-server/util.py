import urllib.request
import yaml
import http.client
import tarfile
import re
import shutil
import tempfile
import logging
import hashlib
import os
import os.path
import subprocess

def create_folder(folder):
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info("created folder %s", folder)
        return True
    except: 
        logging.error("could not create %s", folder)
        return False

# return hash of string in defined length
def get_hash(string, length):
    h = hashlib.sha256()
    h.update(bytes(string, 'utf-8'))
    response_hash = h.hexdigest()[:length]
    return response_hash

def get_statuscode(url):
    url_split = url.split("/")
    host = url_split[2]
    path = "/" +"/".join(url_split[3:])
    conn = http.client.HTTPConnection(host)
    conn.request("HEAD", path) 
    return conn.getresponse().status

def get_latest_release(distro):
    with open(os.path.join("distributions", distro, "releases"), "r") as releases:
        return releases.readlines()[-1].strip()
    return None

def get_release_config(distro, release):
    config_path = os.path.join("distributions", distro, (release + ".yml"))
    if os.path.exists(config_path):
        with open(config_path, "r") as release_config:
            return yaml.load(release_config.read())

    return None

def get_supported_targets(distro, release):
    response = {}
    targets = get_release_config(distro, release)
    if targets:
        for target in targets["supported"]:
            subtarget = None
            if "/" in target:
                target, subtarget = target.split("/")
            if not target in response:
                response[target] = []
            if subtarget:
                response[target].append(subtarget)
        return response
    return None
