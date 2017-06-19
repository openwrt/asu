import unittest
from replacement_table import ReplacementTable
import logging

class ReplacementTableTest(unittest.TestCase):
    def setUp(self):
        self.latest_version = "17.01.0"
        self.request = {}
        self.request["distro"] = "LEDE"
        self.request["version"] = "16.04"
        self.request["target"] = "x86"
        self.request["subtarget"] = "generic"
        self.request["packages"] = [
            "kmod-ipv6",
            "openvpn",
            "polarssl",
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
	    "kmod-button-hotplug",
	    "kmod-igb"
	]
        self.rp = ReplacementTable()
        self.rp.load_tables()
        print(self.rp.tables)

    def test_request(self):
        response = self.rp.check_packages(self.request["distro"], self.request["version"], self.latest_version, self.request["packages"])
        print(response)



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
