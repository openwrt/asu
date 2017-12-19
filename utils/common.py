import urllib.request
import gnupg
import json
import yaml
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
    try:
        urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        return e.code
    else:
        return 200

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
    with open(os.path.join(key_folder, "public"), "r") as pubkey_file:
        return pubkey_file.readlines()[1].strip()

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

def usign_verify(file_path, pubkey):
    key_folder = get_folder("key_folder")
    # better way then using echo?
    cmdline = ['echo', pubkey, '|', 'usign', '-V', '-p', '-', '-m', file_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=key_folder,
        stdout=subprocess.PIPE,
        shell=False,
        stderr=subprocess.STDOUT
    )
    output, _ = proc.communicate()
    return_code = proc.returncode
    if not return_code == 0:
        return False
    else:
        return True

def pkg_hash(packages):
    packages = sorted(list(set(packages)))
    package_hash = get_hash(" ".join(packages), 12)
    database.insert_hash(package_hash, packages)
    return package_hash

def request_hash(distro, release, target, subtarget, profile, packages):
    request_array = [distro, release, target, subtarget, profile, pkg_hash]
    return(get_hash(" ".join(request_array), 12))

def get_distros():
    return(os.listdir(config.get("distro_folder")))

