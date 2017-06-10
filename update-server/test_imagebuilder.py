import unittest
import os
from database import Database
from imagebuilder import ImageBuilder
from queue import Queue	
import logging

class ImageBuilderTest(unittest.TestCase):
    def setUp(self):
        self.database = Database
        self.queue = Queue()	
        self.building = ""
        self.request = {}
        self.request["distro"] = "LEDE"
        self.request["version"] = "17.01.1"
        self.request["target"] = "x86"
        self.request["subtarget"] = "64"
        self.request["board"] = "foobar"
        self.request["packages"] = [
	    "mkf2fs",
	    "opkg",
	    "iperf",
	    "wavemon",
	    "busybox",
	    "odhcpd",
	    "base-files",
	    "partx-utils",
	    "netifd",
	    "kmod-r8169",
	    "dnsmasq",
	    "firewall",
	    "odhcp6c",
	    "fstools",
	    "uclient-fetch",
	    "uci",
	    "dropbear",
	    "mtd",
	    "logd",
	    "iptables",
	    "e2fsprogs",
	    "vim",
	    "ip6tables",
	    "luci",
	    "kernel",
	    "kmod-button-hotplug",
	    "kmod-igb"
	]

        imagebuilder = ImageBuilder("lede", "17.01.1", "x86", "generic")
        # this does not download imagebuilder every time
        if not imagebuilder.created():
            imagebuilder.download()
        self.assertTrue(imagebuilder.created())

    def test_init_imagebuilder(self):
        imagebuilder = ImageBuilder("lede", "17.01.1", "x86", "64")
        self.assertEquals(imagebuilder.path, "imagebuilder/lede/17.01.1/x86/64/lede-imagebuilder-17.01.1-x86-64.Linux-x86_64")

    def test_package_list(self):
        imagebuilder = ImageBuilder("lede", "17.01.1", "x86", "generic")
        imagebuilder.run()
        default_packages_should = ['base-files', 'libc', 'libgcc', 'busybox', 'dropbear', 'mtd', 'uci', 'opkg', 'netifd', 'fstools', 'uclient-fetch', 'logd', 'partx-utils', 'mkf2fs', 'e2fsprogs', 'kmod-button-hotplug', 'dnsmasq', 'iptables', 'ip6tables', 'ppp', 'ppp-mod-pppoe', 'firewall', 'odhcpd', 'odhcp6c']

        self.assertEqual(imagebuilder.default_packages, default_packages_should)

if __name__ == '__main__':
    unittest.main()
