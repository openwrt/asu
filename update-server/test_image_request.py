import unittest
from image_request import ImageRequest
from queue import Queue	
import logging

class ImageRequestTest(unittest.TestCase):
    def setUp(self):
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

    def test_good_request(self):
        image_request = ImageRequest(self.request, self.queue, self.building)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"queue": 1}', 201))

    def test_bad_missing_version(self):
        request = self.request
        request.pop("version")
        image_request = ImageRequest(request, self.queue, self.building)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "missing parameters - need distro version target subtarget board packages"}', 400))

    def test_bad_target(self):
        request = self.request
        request["target"] = "this_is_bad"
        image_request = ImageRequest(request, self.queue, self.building)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "unknown target this_is_bad/64"}', 400))

if __name__ == '__main__':
    unittest.main()
