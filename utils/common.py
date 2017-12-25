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

def gpg_init():
    gpg_folder = config.get_folder("keys_private")
    os.chmod(gpg_folder, 0o700)
    gpg = gnupg.GPG(gnupghome=gpg_folder)

def gpg_gen_key(email):
    gpg_folder = config.get_folder("keys_private")
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    if os.listdir(gpg_folder + "/private-keys-v1.d") == []:
        input_data = gpg.gen_key_input(name_email=email, passphrase=config.get("gpg_pass"))
        key = gpg.gen_key(input_data)
    pubkey = gpg.export_keys(gpg.list_keys()[0]["keyid"])
    with open(config.get("keys_private") + "/public.gpg", "w") as f:
        f.write(pubkey)

def gpg_recv_keys():
    gpg_folder = config.get_folder("keys_private")
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    key_array = ["08DAF586 ", "0C74E7B8 ", "12D89000 ", "34E5BBCC ", "612A0E98 ", "626471F1 ", "A0DF8604 ", "A7DCDFFB ", "D52BBB6B"]
    gpg.recv_keys('pool.sks-keyservers.net', *key_array)

def gpg_verify(path):
    gpg_folder = config.get_folder("keys_public")
    gpg = gnupg.GPG(gnupghome=gpg_folder)
    verified = gpg.verify_file(open(os.path.join(path, "sha256sums.gpg"), "rb"), os.path.join(path, "sha256sums"))
    return verified.valid


def usign_init(comment=None):
    keys_private = config.get_folder("keys_private")
    if not os.path.exists(keys_private + "/secret"):
        print("create keypair")
        cmdline = ['usign', '-G', '-s', 'secret', '-p', 'public']
        if comment:
            cmdline.extend(["-c", comment])
        proc = subprocess.Popen(
            cmdline,
            cwd=keys_private,
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

def usign_pubkey():
    keys_private = config.get_folder("keys_private")
    with open(os.path.join(keys_private, "public"), "r") as pubkey_file:
        return pubkey_file.readlines()[1].strip()

def usign_sign(image_path):
    cmdline = ['usign', '-S', '-s', 'secret', '-m', image_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=config.get_folder("keys_private"),
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
    keys_private = config.get_folder("keys_private")
    # better way then using echo?
    cmdline = ['echo', pubkey, '|', 'usign', '-V', '-p', '-', '-m', file_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=keys_private,
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

