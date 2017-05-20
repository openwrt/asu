# ubus commands

### receive release information

	ubus call system board

```
{
	"kernel": "4.9.20",
	"hostname": "LEDE",
	"system": "QEMU Virtual CPU version 2.5+",
	"model": "QEMU Standard PC (i440FX + PIIX, 1996)",
	"release": {
		"distribution": "LEDE",
		"version": "SNAPSHOT",
		"revision": "r4144-a131b892ea",
		"codename": "reboot",
		"target": "x86\/64",
		"description": "LEDE Reboot SNAPSHOT r4144-a131b892ea"
	}
}
```

### reveive user installed packages
	
	ubus call installed getInstalledPkgs

```
{
	"installed_pkgs": [
		"mkf2fs",
		"opkg",
		"ubus",
		"rpcd",
		"busybox",
		"odhcpd",
		"libiwinfo",
		"kmod-lib-crc-ccitt",
		"r8169-firmware",
		"kmod-pppoe",
		"kmod-pppox",
		"kmod-ipt-conntrack",
		"..."
	}
}
```
