import urllib.request
import gnupg
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
from config import Config
import subprocess

config = Config()

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

def get_root():
    return os.path.dirname(os.path.realpath(__file__))

def get_dir(requested_folder):
    folder = config.get(requested_folder)
    if folder:
        if create_folder(folder):
            return folder

    default_folder = os.path.join(get_root(), requested_folder)
    if create_folder(default_folder):
        return default_folder
    else:
        quit()

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

def setup_gnupg():
    gpg_folder = get_dir("gnupg")
    os.chmod(gpg_folder, 0o700)
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    key_array = ["08DAF586 ", "0C74E7B8 ", "12D89000 ", "34E5BBCC ", "612A0E98 ", "626471F1 ", "A0DF8604 ", "A7DCDFFB ", "D52BBB6B"]
    gpg.recv_keys('pool.sks-keyservers.net', *key_array)

def check_signature(path):
    gpg_folder = get_dir("gnupg")
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    print("xxxx", path)
    verified = gpg.verify_file(open(os.path.join(path, "sha256sums.gpg"), "rb"), os.path.join(path, "sha256sums"))
    return verified.valid

