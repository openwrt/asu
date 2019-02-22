import urllib.request
import hashlib
import os
import os.path
import subprocess
import urllib
from email.utils import parsedate
from datetime import datetime

from asu.utils.config import Config

config = Config()

# return hash of string in defined length
def get_hash(string, length):
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_packages_hash(packages):
    return get_hash(" ".join(sorted(list(set(packages)))), 12)


def get_request_hash(request):
    if "packages" in request:
        if request["packages"]:
            request["packages_hash"] = get_packages_hash(request["packages"])
    if "defaults" in request:
        if request["defaults"]:
            request["defaults_hash"] = get_hash(request["defaults"], 32)
    request_array = [
        request["distro"],
        request["version"],
        request["target"],
        request["profile"],
        request.get("defaults_hash", ""),
        request.get("packages_hash", ""),
    ]
    return get_hash(" ".join(request_array), 12)


def get_statuscode(url):
    """get statuscode of a url"""
    try:
        request = urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        return e.code
    else:
        return request.getcode()


def get_header(url):
    """get headers of a url"""
    try:
        return urllib.request.urlopen(url).info()
    except urllib.error.HTTPError:
        return None


def get_last_modified(url):
    """returns the last-modified header value as datetime object"""
    headers = get_header(url)
    if headers:
        return datetime(*parsedate(headers["last-modified"])[:6])


def usign_init(comment=None):
    keys_private = config.get_folder("keys_private")
    if not os.path.exists(keys_private + "/secret"):
        print("create keypair")
        cmdline = ["usign", "-G", "-s", "secret", "-p", "public"]
        if comment:
            cmdline.extend(["-c", comment])
        proc = subprocess.Popen(
            cmdline,
            cwd=keys_private,
            stdout=subprocess.PIPE,
            shell=False,
            stderr=subprocess.STDOUT,
        )
        output, erros = proc.communicate()
        return_code = proc.returncode
        if not return_code == 0:
            print("output", output)
            print("errors", errors)
            return False
    else:
        print("found keys, ready to sign")
    return True


def usign_pubkey():
    keys_private = config.get_folder("keys_private")
    with open(os.path.join(keys_private, "public"), "r") as pubkey_file:
        return pubkey_file.readlines()[1].strip()


def usign_sign(image_path):
    cmdline = ["usign", "-S", "-s", "secret", "-m", image_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=config.get_folder("keys_private"),
        stdout=subprocess.PIPE,
        shell=False,
        stderr=subprocess.STDOUT,
    )
    output, erros = proc.communicate()
    return_code = proc.returncode
    if not return_code == 0:
        return False
    return True


def usign_verify(file_path, pubkey):
    keys_private = config.get_folder("keys_private")
    # better way then using echo?
    cmdline = ["echo", pubkey, "|", "usign", "-V", "-p", "-", "-m", file_path]
    proc = subprocess.Popen(
        cmdline,
        cwd=keys_private,
        stdout=subprocess.PIPE,
        shell=False,
        stderr=subprocess.STDOUT,
    )
    output, _ = proc.communicate()
    return_code = proc.returncode
    if not return_code == 0:
        return False
    else:
        return True
