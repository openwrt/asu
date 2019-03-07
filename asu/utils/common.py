import hashlib


def get_hash(string, length):
    """Return sha256 hash truncated to length"""
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_packages_hash(packages):
    """Return sha256 hash of sorted packages array length 12"""
    return get_hash(" ".join(sorted(list(set(packages)))), 12)


def get_request_hash(request):
    """Return sha256 hash of image request"""
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
