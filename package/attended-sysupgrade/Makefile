#
# Copyright (C) 
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=attended-sysupgrade
PKG_VERSION:=1
PKG_RELEASE:=2
PKG_LICENSE:=GPL-2.0

include $(INCLUDE_DIR)/package.mk

define Package/attended-sysupgrade
  SECTION:=system
  CATEGORY:=Sysupgrade
  MAINTAINER:=Paul Spooren <paul@spooren.de>
  TITLE:=Enables easy Sysupgrades via Luci
  DEPENDS:= +rpcd +luci
endef

define Package/attended-sysupgrade/description
 Foobar more to come
endef

define Build/Compile
endef

define Build/Configure
endef

define Package/attended-sysupgrade/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/view/
	$(INSTALL_BIN) ./luci/view/attended-sysupgrade.htm $(1)/usr/lib/lua/luci/view/attended-sysupgrade.htm

	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller/
	$(INSTALL_BIN) ./luci/controller/attended-sysupgrade.lua $(1)/usr/lib/lua/luci/controller/attended-sysupgrade.lua

	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d/
	$(INSTALL_BIN) ./rpcd/attended-sysupgrade.json $(1)/usr/share/rpcd/acl.d/attended-sysupgrade.json

	$(INSTALL_DIR) $(1)/usr/libexec/rpcd/
	$(INSTALL_BIN) ./files/attended-sysupgrade $(1)/usr/libexec/rpcd/attended-sysupgrade
endef

$(eval $(call BuildPackage,attended-sysupgrade))
