# Attended Sysupgrade (GSoC 2017)

This project intend to simplify the sysupgrade process of LEDE/LibreMesh. The provided tools here offer an easy way to reflash the router with a new release or package updates, without the need of `opkg` installed. 

![luci-app-attendedsysupgrade-screenshot](https://screenshots.firefoxusercontent.com/images/72b35ace-4fe2-4bba-9996-786e753d34b2.png)

### Created LEDE packages

* [`rpcd-mod-attendedsysupgrade`](https://github.com/openwrt/packages/tree/master/utils/rpcd-mod-attendedsysupgrade)

Offers a function to perform a sysupgrade via ubus. 

* [`rpcd-mod-packagelist`](https://github.com/openwrt/packages/tree/master/utils/rpcd-mod-packagelist)

Has the function `list` to show all user installed packages without the need of `opkg` installed. 

* [`luci-app-attendedsysupgrade`](https://github.com/openwrt/luci/tree/master/applications/luci-app-attendedsysupgrade)

Add a view to the Luci system tab called "Attended Sysupgrade". Offers a button to search for updates and if found, to flash the image created by the update server. 

**Dependencies:**
* `rpcd`
	Used by both `rpcd-*` packages
* `uhttpd-mod-ubus`
	Communication between the Browser and the Router
* `cgi-io`
	Upload image from Browser to Router

### Server side

The server listens to update and image requests. Images are auto generated if the requests was valid. LEDE ImageBuilder is automatically setup up on first request of distribution, release, target & subtarget. 

All requests are stored in a queue and build by workers. 

## API

To communicate with the update server one have to distinguish between *update request*, *update response*, *image request* and *image response*. The different types are explained below.

### Update request

Sends information about the device to the server to see if a new distribution release or package updates are available. An *update request* could look like this:

| key 	| value | information 	|
| --- 	| --- 	| --- 		|
| `distro` | `LEDE` | installed distribution |
| `version` | `17.01.0` | installed release |
| `target` | `ar71xx` | |
| `subtarget` | `generic` | |
| `packages` | `{libuci-lua: 2017-04-12-c4df32b3-1, cgi-io: 3, ...}` | all user installed packages |

Most information can be retrieved via `ubus call system board`. Missing information can be gathered via the `rpcd-mod-packagelist` package.
`packages` contains all user installed packages. Packages installed as an dependence are excluded.

### Update response

The server validates the request. Below is a possible response for a new release:

| key 		| value 	| information 	|
| --- 		| --- 		| --- 		|
| `version` 	| `17.01.2` 	| newest release |
| `updates` 	| `{luci-lib-jsonc: [git-17.230.25723-2163284-1, git-17.228.56579-209deb5-1], ...}` | Package updates `[new_version, current_version]` |
| `packages` 	| `[libuci-lua, cgi-io: 3, ...]` | All packages for the new image |


The client should check the status code:

| status 	| meaning 				| information 	|
| --- 		| --- 					| --- 			|
| 500 		| error					| see `error` in response | 
| 503 		| server overload	   		| see `error` in response | 
| 204 		| no updates				| | 
| 201 		| imagebuilder not ready		| setting up imagebuilder, retry soon | 
| 200		| new release / new package updates	| see `version` and `updates` in response |

An release update does not ignore package updates for the following reason. Between releases packages names may change, packages are dropped or merged. The *update reponse* contains all packages included changed ones.

### Image request

The *update reponse* should be shown to the user in a readable way. Once the user decides to perform the sysupgrade a new request is send to the server called *image request*

| key 		| value 				| information 	|
| --- 		| --- 					| --- 		|
| `distro` 	| `LEDE` 				| installed distribution |
| `version`	| `17.01.2` 				| installed release |
| `target` 	| `ar71xx` 				| |
| `subtarget` 	| `generic` 				| |
| `board` 	| `tl-wdr4300-v1` 			| `board_name` of `ubus call system board` |
| `model` 	| `TP-Link TL-WDR4300 v1` 		| `model` of `ubus call system board` |
| `packages` 	| `[libuci-lua, cgi-io: 3, ...]` 	| All packages for the new image |

The *image request* is nearly the same as the *update request* before, except only containing package names without version and adding `board` and `model`. While the update server builds the requested image the clients keeps polling the server, sending *exacly* the same *image request*. The client _does not_ receive a ticket ID or anything similar. This is due to the situation when same devices poll in parallel only one build job is triggered, resulting in the same image for all devices.

### Image response

| key 	| value | information 	|
| --- 	| --- 	| --- 		|
| `checksum` | `8b32f569dca8dcd780414f7850ed11e8` | md5 |
| `filesize` | `5570113` |  |
| `url` | `https://betaupdate.libremesh.o…x86-64-Generic-sysupgrade.bin` | download link |

The `status` code has again different meanings.

| status 	| meaning 				| information 	|
| --- 		| --- 					| --- 			|
| 500		| build faild				| see `error`	|
| 503 		| server overload   			| see `error` in response | 
| 201		| queued				| requests wait to build |
| 206		| building				| building right now |
| 200		| ready					| build finished successful |
