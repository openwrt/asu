import json
from database import Database
import yaml
from config import Config
import os

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
database = Database()

def load_tables():
    config = Config()
    distros = {}
    for distro in config.get("distributions").keys():
        distros[distro] = {}
        releases = yaml.load(open(os.path.join("distributions", distro, "releases.yml")).read())
        for release in releases:
            release = str(release)
            release_replacements_path = os.path.join("distributions", distro, (release + ".yml"))
            if os.path.exists(release_replacements_path):
                with open(release_replacements_path, "r") as release_replacements_file:
                    replacements = yaml.load(release_replacements_file.read())
                    if replacements:
                        if "transformations" in replacements:
                            insert_replacements(distro, release, replacements["transformations"])

def insert_replacements(distro, release, transformations):
    for package, action in transformations.items():
        if not action:
            # drop package
            #print("drop", package)
            database.insert_transformation(distro, release, package, False, False)
        elif type(action) is str:
            # replace package
            #print("replace", package, "with", action)
            database.insert_transformation(distro, release, package, action, False)
        elif type(action) is dict:
            for choice, context in action.items():
                if context is True:
                    # set default
                    #print("default", choice)
                    database.insert_transformation(distro, release, package, choice, False)
                elif context is False:
                    # possible choice
                    #print("choice", choice)
                    pass
                elif type(context) is list:
                    for dependencie in context:
                        # if context package exists
                        #print("dependencie", dependencie, "for", choice)
                        database.insert_transformation(distro, release, package, choice, dependencie)

load_tables()
