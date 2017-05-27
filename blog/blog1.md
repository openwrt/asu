# GSoC 2017 - Attended Sysupgrades

Hello, my name is Paul Spooren and I'll be working on attended sysupgrades this Google Summer of Code. I'm 24 years old and studying computer science at the university of Leipzig. With this blog post I try to explain my project, the advantages and it's challenges.

## Topic Change from captive portals.

When I applied to GSoC my first application covered the implementation of "Captive Portals" [^captiveportals] for the LibreMesh [^libremesh]. After discussing details with my mentors we decide to switch the project. 
The main shortcomings where the following:
* Captive portals need testing on all kind of devices, Apple devices using a different approach than Android, Linux distribution differ, all kinds of Microsoft's Windows as well. Testing would claim to much effort to provide a stable solution
* Captive portals usually intercept HTTP traffic and changing it content with a redirect to the login provider's splash page. This does not work with encrypted traffic (https) and would result in certification errors.

Discussing what has generic use to OpenWRT/LEDE and LibreMesh we came up with the topic of a simple sysupgrade solution and fixed on that.

## What are attended sysupgrades?

Performing updates on routers is quite different from full Linux distribution. It's not always sustainable to do release upgrade via a packet manager. Instead it's usually required to re-flash the system image. Depending on the installed packages an image rebuild may be to complex for regular users. A more convenient way is needed.

The main idea is to provide a simple function within the web interface to automatically download a custom sysupgrade-image with all currently installed packages preinstalled. 
An opt-in option would check for new releases and notify via luci(-ng)[^luci][^lucing] or command line.

This approach would also help to upgrade a router without full computer hardware. The web interface can be accessed from mobile phones and as no complicated image downloading is required all users can perform sysupgrades on their own.

Distributions like LibreMesh may have a more frequent package release cycle and devices may don't offer `opkg`[^opkg] due to limited flash storage. The simple sysupgrade approach could be used as a `opkg` replacement for these special cases and keep devices up to date.

## How does it work?

The web interface will have a new menu entry called "Attended Upgrade". The page send the currently installed release to the server and checks it response. If an upgrade is available a notification will be shown. A click on the download button sends a request to the server and downloads the image. Another click uses the sysupgrade mechanism and installs the image. After reboot the system should run as excepted with all before installed packages included.

This project will implement an "image as a service" server side which provides custom build images depending on installed packages. A JSON API will enable routers to send requests for custom images. Build images will be stored and reused for other requests with the same package selection and device model.
A simple FIFO queue will manage all builds requests. Created images will be stored by priority queue system so most requested combination are always in cache. 

## Challenges

* With new releases packages may be renamed. This can be due to a split after growing in size as more and more features are added or if different versions of a tool exists. The update server has to know about all renamed packages and created an image with all needed programs. Therefore a replacement table will be created which can be managed by the community. Merges, splits and new naming convention will be covered. To make updating easy the server will try to handle changed names as automatic as possible. If there exists different possibilities to choose from there will be a menu in the web interface. 

* Currently luci is the de facto web interface of LEDE/OpenWRT. Eventually it will be replaced by luci-ng with a modern JavaScript framework. All router sided routing has to be easily portable to the new web interface. 

## Implementation details

The main logic will happen within the browser and so can use secure HTTPS to communicate with the update server. The users browser communicates between router and upgrade server.

Once opened the upgrade view will ask the router via an `rpcd`[^rpcd] call to receive the installed release and send the version to the update server as an *update availability request*. The server will answer with an *update availability response* containing information about the update if exists or a simple status 204 (No Content) code. If a new release exists the web interface will perform another `rpcd` request to get details of the device, installed packages versions and flash storage. The information are then combined and send as an JSON request to the update server as an *image request*.

The image requests would look something like this:

	{
		"distro": "LEDE",
		"version": "17.01.0",
		"revision": "48d71ab502",
		"target": "ar71xx",
		"subtarget": "generic",
		"machine": "TP-LINK CPE510/520",
		"packages": [ 
			"ppp-mod-pppoe": "2.4.7-11",
			"kmod-ipt-nat": "4.9.20-1",
			...
		]
	}

Once the update server received the request it will check if the image was created before. If so it will deliver the update image straight away. If the request (meaning device and package combination) was done for the first time a couple of checks will be done if the image can be created. If all checks pass the wrapper around the LEDE ImageBuilder[^imagebuilder] will be queued and a build status API is polled by the web interface. Once created a download link is provided. 

In the unlikely event of an unsolvable package problem the replacement table can't fix itself the user will be asked to choose from a list. The new combination of packages will be send to the server as a new request resulting in an sysupgrade image. This approach still needs some evaluation if utilizable and really needed.

Using the ImageBuilder offers an generic way to offer sysupgrades for different distribution. The image builder feeds can be extended to include distribution specific packages like LibreMesh package feed[^limefeed]

The replacement table could be implemented as followed:

    # ./lede/replacements/17.01.1
	{
		"libmicrohttpd": [
			"libmicrohttpd-no-ssl": [
				"default": true
			],
			"libmicrohttpd": []
		},
		"openvpn": [
			"openvpn-openssl" [
				"default": true
			],
			"openvpn-mbedtls": [
				"installed" [ 
					"polarssl", 
					"mbedtls"
				]
			],
			"openvpn-nossl": []
		],
		"polarssl": [
			"mbedtls": [
				"default": true
			]
		]
	}	


`libmicrohttpd` was replaced by `libmicrohttpd-no-ssl` (installed as default) and  `libmicrohttpd`. 
`openvpn` splittet into various packages depending on the installed crypto library, `openvpn-openssl` is the default while `openvpn-mbedtls` is only installed if `mbedtls` (or it's prior name `polarssl`) was installed before.

For better readability the `yaml` format could be preferred. 

## Possible features

* The current design is an attended upgrade triggered by and dependent on the web interface. A feature could be to add logic to the command line as well.

* Once the sysupgrade is possible via shell, an unattended sysupgrade would be possible. A testing and a release channel could enable unattended upgrades for tested images (device specific) only. If an image works after an attended upgrade it could be tagged and offered via the release channel.

* Mesh protocols may change and outdated routers loose connectivity. A possible solution to upgrade the devices losing contact could be to automatically login the outdated routers to updated routers open access points, perform an update and reconnect to the mesh.

[^libremesh]: https://libremeshorg
[^captiveportals]: https://wiki.freifunk.net/ideas#LibreMesh_Captive_Portal_and_Access_Control
[^luci]: https://github.com/openwrt/luci
[^lucing]: https://github.com/jow-/luci-ng
[^rpcd]: https://lede-project.org/docs/guide-developer/rpcd
[^imagebuilder]: https://github.com/lede-project/source/tree/master/target/imagebuilder
[^limefeed]: https://github.com/libremesh/lime-packages.git
[^opkg]: https://lede-project.org/docs/user-guide/opkg
