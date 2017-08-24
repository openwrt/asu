# Demos

To test the update server you can use the `shell scripts` or install the current `snapshot` build on your router.

## Via shell script

## request images from the server

run `./image-request.sh <config>.json` to request a specific image.

Modify the `json` files as needed. If the request isn't valid the server respond with an error message.

## Example

    $ ./image-request.sh snapshot_loco.json
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    setting up imagebuilder - please wait
    currently building - please wait
    currently building - please wait
    build successfull
    {"checksum": "e07bced167562101fb9dd361cab320a4", "url": "https://betaupdate.libremesh.org/download/lede/snapshot/ar71xx/generic/ubnt-loco-m-xw/lede-snapshot-c3d0e612c9917c7-ar71xx-generic-ubnt-loco-m-xw-sysupgrade.bin", "filesize": 3407876}

## Via snapshot installation

Install the following three packages (in that order) from the [snapshot repo](http://downloads.lede-project.org/snapshots/packages/) via `opkg install <url>.ipk`.

* `rpcd-mod-packagelist` from packages/
* `rpcd-mod-attendedsysupgrade` from packages/
* `luci-app-attendedsysupgrade` from luci/

Reboot.

## Example

    opkg update
    opkg install http://downloads.lede-project.org/snapshots/packages/i386_pentium4/packages/rpcd-mod-packagelist_0.1-1_i386_pentium4.ipk
    opkg install http://downloads.lede-project.org/snapshots/packages/i386_pentium4/packages/rpcd-mod-attendedsysupgrad
    e_1-1_i386_pentium4.ipk
    opkg install http://downloads.lede-project.org/snapshots/packages/i386_pentium4/luci/luci-app-attendedsysupgrade_git-17.227.62661-3d338ee-1_all.ipk
    reboot
