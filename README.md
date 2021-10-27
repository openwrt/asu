# Attendedsysupgrade Server for OpenWrt (GSoC 2017)

[![codecov](https://codecov.io/gh/aparcar/asu/branch/master/graph/badge.svg)](https://codecov.io/gh/aparcar/asu)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPi](https://badge.fury.io/py/asu.svg)](https://badge.fury.io/py/asu)

This project simplifies the sysupgrade process for upgrading the firmware of
devices running OpenWrt or distributions based on it. These tools offer an easy
way to reflash the router with a new firmware version
(including all packages) without the need to use `opkg`.

It's called Attended SysUpgrade (ASU) because the upgrade process is not started
automatically, but is initiated by a user who waits until it's done.

ASU is based on an API (described below) to request custom firmware images with
any selection of packages pre-installed. This avoids the need to set up a build
environment, and makes it possible to create a custom firmware image even using
a mobile device.

## Clients of the Sysupgrade Server

### OpenWrt Firmware Selector

Simple web interface using vanilla JavaScript currently developed by @mwarning.
It offers a device search based on model names and show links either to
[official images](https://downloads.openwrt.org/) or requests images via the
_asu_ API. Please join in the development at
[GitLab repository](https://gitlab.com/openwrt/web/firmware-selector-openwrt-org)

![ofs](misc/ofs.png)

### LuCI app

The package
[`luci-app-attendedsysupgrade`](https://github.com/openwrt/luci/tree/master/applications/luci-app-attendedsysupgrade)
offers a simple tool under `System > Attended Sysupgrade`. It requests a new
firmware image that includes the current set of packages, waits until it's built
and flashes it. If "Keep Configuration" is checked in the GUI, the device
upgrades to the new firmware without any need to re-enter any configuration or
re-install any packages.

![luci](misc/luci.png)

### CLI

The [`auc`](https://github.com/openwrt/packages/tree/master/utils/auc) package
performs the same process as the `luci-app-attendedsysupgrade`
from SSH/the command line.

![auc](misc/auc.png)

## Server

The server listens for image requests and, if valid, automatically generates
them. It coordinates several OpenWrt ImageBuilders and caches the resulting
images in a Redis database. If an image is cached, the server can provide it
immediately without rebuilding.

### Active server

- [sysupgrade.openwrt.org](https://sysupgrade.openwrt.org)
- [asu.aparcar.org](https://asu.aparcar.org)
- ~~[chef.libremesh.org](https://chef.libremesh.org)~~ (`CNAME` to
  asu.aparcar.org)

## Run your own server

Redis is required to store image requests:

    sudo apt install redis-server tar

Install _asu_:

    pip install asu

Create a `config.py`.
You can use `misc/config.py` as an example.

Start the server via the following commands:

    export FLASK_APP=asu.asu  # set Flask app to asu
    flask janitor update      # download upstream profiles/packages - this runs forever
    flask run                 # run development server - this runs forever

Start the worker via the following comand:

    rq worker                 # this runs forever

### Docker

Run the service inside multiple Docker containers. The services include the _
ASU_ server itself, a _janitor_ service which fills the Redis database with
known packages and profiles as well as a `rqworker` which actually builds
images.

Currently all services share the same folder and therefore a very "open" access
is required. Suggestions on how to improve this setup are welcome.

    mkdir ./asu-service/
    chmod 777 ./asu-service/
    docker-compose up

A webserver should proxy API calls to port 8000 of the `server` service while
the `asu/` folder should be file hosted as-is.

### Production

It is recommended to run _ASU_ via `gunicorn` proxied by `nginx` or
`caddyserver`. Find a possible server configurations in the `misc/` folder.

The _ASU_ server will try `$PWD/config.py` and `/etc/asu/config.py` to find a
configuration. Find an example configuration in the `misc/` folder.

    pip install gunicorn
    gunicorn "asu.asu:create_app()"

Ideally use the tool `squid` to cache package indexes, which are reloaded every
time an image is built. Find a basic configuration in at `misc/squid.conf`
which should be copied to `/etc/squid/squid.conf`.

If you want to use `systemd` find the service files `asu.service` and
`rqworker.service` in the `misc` folder as well.

### Development

After cloning this repository, create a Python virtual environment and install
the dependencies:

    python3 -m venv .direnv
    source .direnv/bin/activate
    pip install -r requirements.txt
    export FLASK_APP=asu.asu  # set Flask app to asu
    export FLASK_APP=tests.conftest:mock_app FLASK_DEBUG=1 # run Flask in debug mode with mock data
    flask run

### API

The API is documented via _OpenAPI_ and can be viewed interactively on the
server:

[https://sysupgrade.openwrt.org/ui/](https://sysupgrade.openwrt.org/ui/)
