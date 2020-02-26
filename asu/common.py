import hashlib
import nacl.signing
import struct
import base64
from pathlib import Path
from flask import current_app


def cwd():
    return Path(current_app.instance_path)


def get_str_hash(string: str, length: int) -> str:
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_file_hash(path: str) -> str:
    BLOCK_SIZE = 65536

    h = hashlib.sha256()
    with open(path, "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            h.update(fb)
            fb = f.read(BLOCK_SIZE)

    return h.hexdigest()


def get_request_hash(request_data):
    request_data["packages_hash"] = get_packages_hash(request_data.get("packages", ""))
    request_array = [
        request_data.get("distro", ""),
        request_data.get("version", ""),
        request_data.get("profile", ""),
        request_data["packages_hash"],
        str(request_data.get("packages_diff", 0)),
    ]
    return get_str_hash(" ".join(request_array), 12)


def get_packages_hash(packages: list) -> str:
    return get_str_hash(" ".join(sorted(list(set(packages)))), 12)


def verify_usign(sig_file, msg_file, pub_key: str) -> bool:
    pkalg, keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(pub_key))
    sig = base64.b64decode(sig_file.read_text().splitlines()[-1])

    pkalg, keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify(msg_file.read_bytes(), sig)
        return True
    except nacl.exceptions.CryptoError:
        return False
