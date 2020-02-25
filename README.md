# Attendedsysupgrade Server for OpenWrt (GSoC 2017)

This project intends to simplify the sysupgrade process of devices running
OpenWrt or distributions based on the former like LibreMesh. The provided tools
here offer an easy way to reflash the router with a new version or package
upgrades, without the need of `opkg` installed.

Additionally it offers an API (covered below) to request custom images with any
selection of packages pre-installed, allowing to create firmware images without
the need of setting up a build environment, even from mobile devices.

## Clients

### Yet another firmware selector

Simple web interface using vanilla JavaScript currently developed by @mwarning.
It offers a device search based on model names and show links either to
[official images](https://downloads.openwrt.org/) or requests images via the
_asu_ API. Please join in the development at the [GitHub
repository](https://github.com/mwarning/yet_another_firmware_selector)

![yafs](misc/yafs.png)

### LuCI app

The package `luci-app-attendedsysupgrade` [still
exists](https://github.com/openwrt/luci/tree/master/applications/luci-app-attendedsysupgrade)
but is currently not usable with the rewritten server implementation. The app
will however be upgraded as soon as possible to be usable again.

## Server

The server listens to image requests and automatically generate them if the
request was valid. This is done by automatically setting up OpenWrt
ImageBuilders and cache images in a Redis database. This allows to quickly
respond to requests without rebuilding existing images again.

### Active server

-   [chef.libremesh.org](https://chef.libremesh.org)

## Run your own server

Redis is required to store image requests:

    sudo apt install redis-server tar

Install _asu_:

    pip install asu

Start the server via the following commands:

    export FLASK_APP=asu  # set Flask app to asu
    flask janitor init    # download upstream profiles/packages
    flask run             # run development server

Start the worker via the following comand:

    rq worker

### Development

After cloning this repository create a Python virtual environment and install
the dependencies:

    python3 -m venv .
    source bin/activate
    pip install -r requirements.txt
    export FLASK_APP=asu  # set Flask app to asu
    export FLASK_DEBUG=1  # run Flask in debug mode (autoreload)
    flask run

## API

### Upgrade check `/api/versions`

The server does no longer offer complex upgrade but only serves static JSON
files including available versions. For now the client must evaluate if the
responded JSON contains a newer version.

### Build request `/api/build`

| key        | value                 | information                              |
| ---------- | --------------------- | ---------------------------------------- |
| `version`  | `SNAPSHOT`            | installed version                        |
| `profile`  | `netgear_wndr4300-v2` | `board_name` of `ubus call system board` |
| `packages` | `["luci", "vim"]`     | Extra packages for the new image         |

### Response `status 200`

```
{
  "bin_dir": "SNAPSHOT/ramips/mt7620/alfa-network_tube-e4g/689292a5569f",
  "build_at": "Mon, 24 Feb 2020 00:00:02 GMT",
  "buildlog": true,
  "enqueued_at": "Sun, 23 Feb 2020 23:59:13 GMT",
  "id": "alfa-network_tube-e4g",
  "image_prefix": "openwrt-689292a5569f-ramips-mt7620-alfa-network_tube-e4g",
  "images": [
    {
      "name": "openwrt-689292a5569f-ramips-mt7620-alfa-network_tube-e4g-squashfs-sysupgrade.bin",
      "sha256": "c14ffd501c8839d737504acf17285a519916830c8df6ca7d281596563c846d1e",
      "type": "sysupgrade"
    }
  ],
  "metadata_version": 1,
  "supported_devices": [
    "alfa-network,tube-e4g"
  ],
  "target": "ramips/mt7620",
  "titles": [
    {
      "model": "Tube-E4G",
      "vendor": "ALFA Network"
    }
  ],
  "version_commit": "r12288-1173719817",
  "version_number": "SNAPSHOT"
}

```

| key        | information                         |
| ---------- | ----------------------------------- |
| `bin_dir`  | relative path to created files      |
| `buildlog` | boolean if buildlog.txt was created |

### Response status codes

The client should check the status code:

| status | meaning                              | information                          |
| ------ | ------------------------------------ | ------------------------------------ |
| `200`  | build finish / upgrade available     | see parameters above                 |
| `202`  | building, queued, imagebuilder setup | building right now or in build queue |
| `400`  | bad request                          | see `error` parameter                |
| `422`  | unknown package                      | unknown package in request           |
| `500`  | build failed                         | see `log` for build log              |
