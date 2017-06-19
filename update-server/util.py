import urllib.request
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

if __name__ == "__main__":
    download_targets()
