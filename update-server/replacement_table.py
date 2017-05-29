import json

# this function will return the package names changed due to the replacement table
# distro: installed distribution
# installedRelease: the currently installed release thats to update
# packages: an array of all user installed packages
def check_packages(distro, installedRelease, packages):
    response = {}

    # only a dummy so far
    response["packages"] = packages

    # this will contain choices to offer in the user interface
    # this is only needed if the dependencie tree can't provide a default answer
    response["choices"] = []
    #response["choices"].append(("bigPkg", ["bigPkg-light", "bigPkg-full"])) 

    return response

# this function will load all replacement tables
def load_tables():
    pass
