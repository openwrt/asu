from pathlib import Path
import base64
import hashlib
import nacl.signing
import struct


def get_str_hash(string: str, length: int = 32) -> str:
    """Return sha256sum of str with optional length

    Args:
        string (str): input string
        length (int): hash length

    Returns:
        str: hash of string with specified length
    """
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_file_hash(path: str) -> str:
    """Return sha256sum of given path

    Args:
        path (str): path to file

    Returns:
        str: hash of file
    """
    BLOCK_SIZE = 65536

    h = hashlib.sha256()
    with open(path, "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            h.update(fb)
            fb = f.read(BLOCK_SIZE)

    return h.hexdigest()


def get_request_hash(request_data: dict) -> str:
    """Return sha256sum of an image request

    Creates a reproducible hash of the request by sorting the arguments

    Args:
        request_data (dict): dict contianing request information

    Returns:
        str: hash of `request_data`
    """
    request_data["packages_hash"] = get_packages_hash(request_data.get("packages", ""))
    request_array = [
        request_data.get("distro", ""),
        request_data.get("version", ""),
        request_data.get("profile", "").replace(",", "_"),
        request_data["packages_hash"],
        str(request_data.get("diff_packages", False)),
    ]
    return get_str_hash(" ".join(request_array), 12)


def get_packages_hash(packages: list) -> str:
    """Return sha256sum of package list

    Duplicate packages are automatically removed and the list is sorted to be
    reproducible

    Args:
        packages (list ): list of packages

    Returns:
        str: hash of `request_data`
    """
    return get_str_hash(" ".join(sorted(list(set(packages)))), 12)


def verify_usign(sig_file: Path, msg_file: Path, pub_key: str) -> bool:
    """Verify a signify/usign signature

    This implementation uses pynacl

    Args:
        sig_file (Path): signature file
        msg_file (Path): message file to be verified
        pub_key (str): public key to use for verification

    Returns:
        bool: Sucessfull verification

    Todo:
         Currently ignores keynum and pkalg

    """
    pkalg, keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(pub_key))
    sig = base64.b64decode(sig_file.read_text().splitlines()[-1])

    pkalg, keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify(msg_file.read_bytes(), sig)
        return True
    except nacl.exceptions.CryptoError:
        return False
