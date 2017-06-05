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


