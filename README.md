# Attendedsysupgrade Server for LEDE/OpenWrt (GSoC 2017)

This project intend to simplify the sysupgrade process of LEDE/LibreMesh. The provided tools here offer an easy way to reflash the router with a new release or package updates, without the need of `opkg` installed.

![luci-app-attendedsysupgrade-screenshot](https://camo.githubusercontent.com/d21d3c2e43993325c0371866b28f09a67ea21902/687474703a2f2f692e696d6775722e636f6d2f653443716841502e706e67)

## Clients

#### [`luci-app-attendedsysupgrade`](https://github.com/openwrt/luci/tree/master/applications/luci-app-attendedsysupgrade)

Add a view to the Luci system tab called "Attended Sysupgrade". Offers a button to search for updates and if found, to flash the image created by the update server.

**Dependencies:**
* `rpcd-mod-rpcsys`
	Used to read list of installed packages and trigger sysupgrade on the target.
* `uhttpd-mod-ubus`
	Communication between the Browser and the Router
* `cgi-io`
	Upload image from Browser to Router

#### [`auc`](https://github.com/openwrt/packages/tree/master/utils/auc)

Add CLI to perform sysupgrades.

**Dependencies:**
* `rpcd-mod-rpcsys`
	Used to read list of installed packages and trigger sysupgrade on the target.
* `usteam-ssl` and `ca-certificates`
	Securely communicate and download firmware from server via https

## Server

The server listens to update and image requests. Images are auto generated if the requests was valid. LEDE ImageBuilder is automatically setup up on first request of distribution, release, target & subtarget.

All requests are stored in a queue and build by workers.

### Active server

* [planetexpress](https://ledeupdate.planetexpress.cc) - thanks @egon0
  You can set this server in `/etc/config/attendedsysupgrade` after installation of a client

## API

### Upgrade check `/api/upgrade-check`

Sends information about the device to the server to see if a new distribution release or package upgrades are available. An *upgrade check* could look like this:

| key	| value | information	|
| ---	| ---	| ---		|
| `distro` | `LEDE` | installed distribution |
| `version` | `17.01.0` | installed release |
| `target` | `ar71xx` | |
| `subtarget` | `generic` | |
| `packages` | `{libuci-lua: 2017-04-12-c4df32b3-1, cgi-io: 3, ...}` | all user installed packages |

Most information can be retrieved via `ubus call system board`. Missing information can be gathered via the `rpcd-mod-rpcsys` package.
`packages` contains all user installed packages plus version. Packages installed as an dependence are excluded as they've been automatically and dependencies may change between releases.

It's also possible to check for a new release without sending packages by removing `packages` from the request.

### Response `status 200`

The server validates the request. Below is a possible response for a new release:

| key		| value		| information	|
| ---		| ---		| ---		|
| `version`		| `17.01.2`		| newest release |
| `upgrades`	| `{luci-lib-jsonc: [git-17.230.25723-2163284-1, git-17.228.56579-209deb5-1], ...}` | Package updates `[new_version, current_version]` |
| `packages`	| `[libuci-lua, cgi-io: 3, ...]` | All packages for the new image |

See [other status codes](#response-status-codes)

An release upgrade does not ignore package upgrades for the following reason. Between releases it possible that package names may change, packages are dropped or merged. The *response* contains all packages included changed ones.

The *upgrade check response* should be shown to the user in a readable way.

### Upgrade request `/api/upgrade-request`

Once the user decides to perform the sysupgrade a new request is send to the server called *upgrade request*.

#### POST

| key		| value					| information	|
| ---		| ---					| ---		|
| `distro`	| `LEDE`				| installed distribution |
| `version`	| `17.01.2`					| installed release |
| `target`	| `ar71xx`				| |
| `subtarget`	| `generic`					| |
| `board`	| `tl-wdr4300-v1`			| `board_name` of `ubus call system board` |
| `[model]`		| `TP-Link TL-WDR4300 v1`		| `model` of `ubus call system board`. This is optional and a fallback |
| `packages`	| `[libuci-lua, cgi-io: 3, ...]`	| All packages for the new image |

The *upgrade request* is nearly the same as the *upgrade check* before, except only containing package names without version and adding `board` and possibly `model`. While the server builds the requested image the clients keeps polling the server sending a `request_hash` via `GET` to the server.

#### GET

If the `request_hash` was retrieved the client should switch to `GET` requests with the hash to save the server from validating the request again.

`api/upgrade-request/<request_hash`

### Response `status 200`

| key	| value | information	|
| ---	| ---	| ---		|
| `sysupgrade` | `https://betaupdate.libremesh.o…x86-64-Generic-sysupgrade.bin` | download link |
| `image_hash` | `27439cbc07fae59` | Hash of image parameters, like distribution, profile, packages and versions |

See [other status codes](#response-status-codes)

### Build request `/api/build-request`

It's also possible to request to build an image. The request is exactly the same as for `upgrade-request`. The response only contains a link to the created `files` or `upgrade-request` parameters if available.

This is a special case for clients that do not necessary require a sysupgrade compatible image. An example is the [LibreMesh Chef](https://chef.libremesh.org) firmware builder.

### Response status codes

The client should check the status code:

| status	| meaning												| information	|
| ---		| ---								| ---			|
| 200		| build finish / upgrade available	| see parameters of `upgrade-check`, `upgrade-request` or `build-request` |
| 202		| building, queued, imagebuilder setup	| building right now, in build queue, imagebuilder not ready. Details are in header `X-Imagebuilder-Status` and `X-Build-Queue-Position` |
| 204		| no updates						| device is up to date. Contains `request_hash` |
| 400		| bad request 						| see `error` parameter |
| 413		| imagesize fail					| produced image too big for device |
| 422		| unknown package					| unknown package in request |
| 500		| build failed						| see `log` for build log	|
| 501		| no sysupgrade						| image build successful but no sysupgrade image created |
| 502		| proxy backend down				| nginx runs but python part is down, likely maintenance |
| 503		| server overload					| please wait ~5 minutes |

### Request data

It's also possible to receive information about build images or package versions, available devices and more. All responses are in `JSON` format.

* `/api/image/<image_hash>`
	Get information about an image. This contains various information stored about the image.

* `/api/manifest/<manifest_hash>`
	Get packages and versions of a manifest. The manifest contains all installed packages of an image. The `manifest_hash` can be received by the api call `/api/image`

* `/api/distro`
	Get all supported distros

* `/api/releases[?distro=<distribution>]`
	Get all supported releases (of distribution)

* `/api/models?distro=&release=&model_search=<search string>`
	Get all supported devices of distro/release that contain the `model_search` string

* `/api/packages_image?distro=&release=&target=&subtarget=&profile=`
	Get all default packages installed on an image
