import urllib.request
import gnupg
import json
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

from utils.config import Config

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

def get_distro_alias(distro):
    with open(os.path.join("distributions", distro, "distro_config.yml"), "r") as releases:
        return yaml.load(releases.read())['distro_alias']
    return None

def get_releases(distro):
    with open(os.path.join("distributions", distro, "distro_config.yml"), "r") as releases:
        return yaml.load(releases.read())['releases']
    return None

def get_latest_release(distro):
    with open(os.path.join("distributions", distro, "distro_config.yml"), "r") as releases:
        return yaml.load(releases.read())['releases'][-1]
    return None

def get_release_config(distro, release):
    config_path = os.path.join("distributions", distro, (release + ".yml"))
    if os.path.exists(config_path):
        with open(config_path, "r") as release_config:
            return yaml.load(release_config.read())

    return None

def get_folder(requested_folder):
    folder = config.get(requested_folder)
    if folder:
        if create_folder(folder):
            return os.path.abspath(folder)

    default_folder = os.path.join(os.getcwdb(), requested_folder)
    if create_folder(default_folder):
        return os.path.abspath(default_folder)
    else:
        quit()

# shortly removed
def get_dir(requested_folder):
    return get_folder(requested_folder)

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
    gpg_folder = get_folder("key_folder")
    os.chmod(gpg_folder, 0o700)
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    key_array = ["08DAF586 ", "0C74E7B8 ", "12D89000 ", "34E5BBCC ", "612A0E98 ", "626471F1 ", "A0DF8604 ", "A7DCDFFB ", "D52BBB6B"]
    gpg.recv_keys('pool.sks-keyservers.net', *key_array)

def check_signature(path):
    gpg_folder = get_folder("key_folder")
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    verified = gpg.verify_file(open(os.path.join(path, "sha256sums.gpg"), "rb"), os.path.join(path, "sha256sums"))
    return verified.valid

def init_usign():
    key_folder = get_folder("key_folder")
    if not os.path.exists(key_folder + "/secret"):
        print("create keypair")
        cmdline = ['usign', '-G', '-s', 'secret', '-p', 'public']
        proc = subprocess.Popen(
            cmdline,
            cwd=key_folder,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT
        )
        output, erros = proc.communicate()
        return_code = proc.returncode
        if not return_code == 0:
            return False
    else:
        print("found keys, ready to sign")
    return True

def get_pubkey():
    key_folder = get_folder("key_folder")
    with open("public", "r") as pubkey_file:
        return pubkey_file.readlines()[1]

def sign_file(image_path):
    key_folder = get_folder("key_folder")
    cmdline = ['usign', '-S', '-s', 'secret', '-m', image_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=key_folder,
        stdout=subprocess.PIPE,
        shell=False,
        stderr=subprocess.STDOUT
    )
    output, erros = proc.communicate()
    return_code = proc.returncode
    if not return_code == 0:
        return False
    return True

def pkg_hash(packages):
    packages = sorted(list(set(packages)))
    package_hash = get_hash(" ".join(packages), 12)
    database.insert_hash(package_hash, packages)
    return package_hash

def request_hash(distro, release, target, subtarget, profile, packages, network_profile):
    request_array = [distro, release, target, subtarget, profile, pkg_hash, network_profile]
    return(get_hash(" ".join(request_array), 12))

def get_network_profiles():
    network_profiles = []
    network_profile_folder = get_folder("network_profile_folder")
    for community in os.listdir(network_profile_folder):
        community_path = os.path.join(network_profile_folder, community)
        if os.path.isdir(community_path) and not community.startswith("."):
            for network_profile in os.listdir(os.path.join(community_path)):
                network_profile_path = os.path.join(community_path, network_profile)
                if os.path.isdir(network_profile_path) and not network_profile.startswith("."):
                    network_profiles.append(os.path.join(community, network_profile))

    return(json.dumps(network_profiles))
