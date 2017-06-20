import urllib.request
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
    return conn.getresponse().status != 404
