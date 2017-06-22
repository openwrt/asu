import unittest
from http import HTTPStatus
from image_request import ImageRequest
from queue import Queue	
import logging

class ImageRequestTest(unittest.TestCase):
    def setUp(self):
        self.last_build_id = 0
        self.request = {}
        self.request["distro"] = "lede"
        self.request["version"] = "17.01.1"
        self.request["target"] = "x86"
        self.request["subtarget"] = "generic"
        self.request["board"] = "foobar"
        self.request["packages"] = [
	    "busybox",
	    "odhcpd",
	    "base-files",
	    "partx-utils",
	    "netifd",
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
	    "ip6tables"
	]

    def test_good_request(self):
        image_request = ImageRequest(self.request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertRegex(response[0], r'"url": "http://.+?/download/lede/.+-sysupgrade\.bin"|')
        self.assertIn(response[1], [HTTPStatus.PARTIAL_CONTENT, HTTPStatus.OK])

    def test_bad_missing_version(self):
        request = self.request
        request.pop("version")
        image_request = ImageRequest(request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "missing parameters - need distro version target subtarget board packages"}', 400))

    def test_bad_target(self):
        request = self.request
        request["target"] = "this_is_bad"
        image_request = ImageRequest(request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "unknown target this_is_bad/generic"}', 400))

    def test_bad_package(self):
        self.request["packages"].append("this_is_bad")
        image_request = ImageRequest(self.request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "could not find package this_is_bad for requested target"}', 400))

    def test_not_supported(self):
        self.request["target"] = "arc770"
        self.request["subtarget"] = "generic"
        image_request = ImageRequest(self.request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('{"error": "target currently not supported arc770/generic"}', 400))

    def test_attended_sysupgrade_package(self):
        self.request["packages"].append("attended-sysupgrade")
        image_request = ImageRequest(self.request, self.last_build_id)
        response = image_request.get_sysupgrade()
        self.assertEqual(response, ('', 206))

if __name__ == '__main__':
    unittest.main()
