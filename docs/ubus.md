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

Same call on a different machine
```
{
	"kernel": "4.4.61",
	"hostname": "wurze2-5",
	"system": "Atheros AR9344 rev 2",
	"model": "TP-Link CPE510 v1.1",
	"release": {
		"distribution": "LEDE",
		"version": "17.01.1",
		"revision": "r3316-7eb58cf109",
		"codename": "reboot",
		"target": "ar71xx\/generic",
		"description": "LEDE Reboot 17.01.1 r3316-7eb58cf109"
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
