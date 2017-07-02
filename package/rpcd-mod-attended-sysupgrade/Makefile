# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=rpcd-mod-attended-sysupgrade
PKG_VERSION:=1
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0

include $(INCLUDE_DIR)/package.mk

define Package/rpcd-mod-attended-sysupgrade
  SECTION:=utils
  CATEGORY:=Base system
  TITLE:=OpenWrt ubus RPC backend server (attended-sysupgrade)
  MAINTAINER:=Paul Spooren <paul@spooren.de>
  DEPENDS:=rpcd +cgi-io +rpcd-mod-packagelist
endef

define Package/rpcd-mod-attended-sysupgrade/description
 Foobar more to come
endef

define Build/Compile
endef

define Build/Configure
endef

define Package/rpcd-mod-attended-sysupgrade/install
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d/
	$(INSTALL_BIN) ./files/rpcd-mod-attended-sysupgrade.json $(1)/usr/share/rpcd/acl.d/rpcd-mod-attended-sysupgrade.json

	$(INSTALL_DIR) $(1)/usr/libexec/rpcd/
	$(INSTALL_BIN) ./files/rpcd-mod-attended-sysupgrade $(1)/usr/libexec/rpcd/rpcd-mod-attended-sysupgrade
endef

$(eval $(call BuildPackage,rpcd-mod-attended-sysupgrade))
