import io
from os.path import abspath, dirname, join

from setuptools import find_packages, setup

from asu import __version__

with io.open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()

base_path = dirname(abspath(__file__))

with open(join(base_path, "requirements.txt")) as req_file:
    requirements = req_file.readlines()

setup(
    name="asu",
    version=__version__,
    url="https://github.com/aparcar/asu",
    maintainer="Paul Spooren",
    maintainer_email="mail@aparcar.org",
    description="Create images for OpenWrt on demand",
    long_description=readme,
    long_description_content_type="text/markdown",
    package_data={"": ["openapi.yml"]},
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    zip_safe=False,
)
