# Attended Sysupgrade (GSoC 2017)

This package will offer an easy way to reflash the router with a new release

*This documentation will grow and is constantly updated*

### ubus package

The package `attended-sysupgrade` offers a function `get_installed_pkgs` to list all user installed packages without the need of `opkg` installed. The function `get_board` returns the board needed as `PROFILE` during image creation. This information is used with release information of `ubus call system board` to request a specific image.

Dependencies:
* rpcd
* luci2-io-helper (to upload sysupgrade.img via webinterface)

A Luci view is created in `System -> Attended Sysupgrade`. It shows some basic information about the device and has an button to search for updates.

Use LEDE-SDK to create the image.

### server side

The server listens to update and image requests. Images are auto generated if the requests was valid. LEDE ImageBuilder is automatically setup up on first request of target/subtarget. 

Currently all server side functions are single threaded and an image requests may times out if the server side needs to long for the ImageBuilder to setup.

## API

To communicate with the update server one have to distinguish between *update request*, *update response*, *image request* and *image response*. The different types are explained below.

### update request

Sends information about the device to the server to see if a new distribution release or package updates are available. An *update request* could look like this:

	{
		"distro": "LEDE",
		"version": "17.01.0",
		"target": "ar71xx",
		"subtarget": "generic",
		"machine": "TP-LINK CPE510/520",
		"packages": {
			"opkg": "2017-05-03-04e279eb-1"
			...
		}   
	}

Most information can be retrieved via `ubus call system board`. Missing information can be gathered via the `attended-sysupgrade` package.
`packages` contains all user installed packages. Packages installed as an dependence are excluded.

### update response

The server validates the request. If all checks pass an response is send, currently only distribution releases are notified. 

	{
		"version": "17.01.1"
		"status": 1
		"error": ""
	}

The client should check the status code:

| status 	| meaning 			| information 	|
| --- 		| --- 				| --- 			|
| 500 		| error				| see `error` in response | 
| 503 		| server overload   | see `error` in response | 
| 204 		| no updates		| | 
| 200		| new release		| see `version` in response |
| 200		| package updates	| see `packages` in response | 

An release update does not ignore package updates for the following reason. Between releases packages names may change. The *update reponse* contains all packages included renamed ones.

### image request

The *update reponse* should be shown to the user in a readable way. Once the user decides to perform the sysupgrade a new request is send to the server called *image request*

	{
		"distro": "LEDE",
		"version": "17.01.1",
		"target": "ar71xx",
		"subtarget": "generic",
		"machine": "TP-LINK CPE510/520",
		"packages": {
			"opkg": "2017-05-03-04e279eb-1"
			...
		}   
	}

The *image request* is nearly the same as the *update request* before, except only containing current versions of release and packages. While the update server builds the requests image the clients keeps polling the server, sending *exacly* the same *image request*. The client _does not_ receive a ticket ID or anything similar. This is due to the situation when same devices poll in parallel only one build job is triggered, resulting in the same image for all devices.

### image response

	{
		"status": 2
		"queue": 3
		"url": "https://update.lede/download/lede/17.01.1/ar71xx/generic/lede-17.01.1-2fe136c15026-ar71xx-generic-<device profile>-sysupgrade.bin"
		"size": 4000000
		"md5": <checksum>
	}

`usign` signatures can bei retrieved via `response['url'] + ".sig"`

The `status` code has again different meanings.

| status 	| meaning 				| information 	|
| --- 		| --- 					| --- 			|
| 500		| build faild			| see `error`	|
| 503 		| server overload   | see `error` in response | 
| 201 		| imagebuilder setup 		|	the LEDE imagebuilder only seen if first build requests for target/subtarget combo |
| 201		| queued				| requests wait to build, see `queue` decreasing |
| 206		| building				| building right now |
| 200		| ready					| build finished successful, see `url` to retrieve image |
