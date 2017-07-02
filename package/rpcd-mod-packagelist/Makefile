# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=rpcd-mod-packagelist
PKG_VERSION:=1
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0

include $(INCLUDE_DIR)/package.mk

define Package/rpcd-mod-packagelist
  SECTION:=utils
  CATEGORY:=Base system
  TITLE:=ubus packagelist
  MAINTAINER:=Paul Spooren <paul@spooren.de>
  DEPENDS:=rpcd @!CLEAN_IPKG
endef

define Package/rpcd-mod-packagelist/description
 Foobar more to come
endef

define Build/Compile
endef

define Build/Configure
endef

define Package/rpcd-mod-packagelist/install
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d/
	$(INSTALL_BIN) ./files/rpcd-mod-packagelist.json $(1)/usr/share/rpcd/acl.d/rpcd-mod-packagelist.json

	$(INSTALL_DIR) $(1)/usr/libexec/rpcd/
	$(INSTALL_BIN) ./files/rpcd-mod-packagelist $(1)/usr/libexec/rpcd/rpcd-mod-packagelist
endef

$(eval $(call BuildPackage,rpcd-mod-packagelist))
