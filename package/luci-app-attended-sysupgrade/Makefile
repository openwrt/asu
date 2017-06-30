# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-attended-sysupgrade
PKG_VERSION:=1
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-attended-sysupgrade
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  MAINTAINER:=Paul Spooren <paul@spooren.de>
  TITLE:=Enables easy Sysupgrades via Luci
  DEPENDS:= +luci-base +rpcd-mod-attended-sysupgrade
endef

define Package/luci-app-attended-sysupgrade/description
 Foobar more to come
endef

define Build/Compile
endef

define Build/Configure
endef

define Package/luci-app-attended-sysupgrade/install
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/view/
	$(INSTALL_BIN) ./files/attended-sysupgrade.htm $(1)/usr/lib/lua/luci/view/attended-sysupgrade.htm

	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller/
	$(INSTALL_BIN) ./files/attended-sysupgrade.lua $(1)/usr/lib/lua/luci/controller/attended-sysupgrade.lua
endef

$(eval $(call BuildPackage,luci-app-attended-sysupgrade))
