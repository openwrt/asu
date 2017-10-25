flavors = {}
flavors["None"] = ""
flavors["lede_vanilla"] = "luci-ssl"
flavors["lime_default"] = "lime-full -dnsmasq"
flavors["lime_mini"] = "lime-basic -opkg -wpad-mini hostapd-mini -kmod-usb-core -kmod-usb-ledtrig-usbport -kmod-usb2 -ppp -dnsmasq -ppp-mod-pppoe -6relayd -odhcp6c -odhcpd -iptables -ip6tables"
flavors["lime_zero"] = "lime-basic-no-ui -wpad-mini hostapd-mini -ppp -dnsmasq -ppp-mod-pppoe -6relayd -odhcp6c -odhcpd -iptables - ip6tables"
flavors["lime_newui_test"] = "lime-full lime-webui-ng-luci lime-app -dnsmasq"
