# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=sysupgrade-image-server
PKG_VERSION:=0.0.1
PKG_RELEASE=$(PKG_SOURCE_VERSION)-1
PKG_LICENSE:=GPL-3.0

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/aparcar/gsoc17-attended-sysupgrade
PKG_SOURCE_SUBDIR:=$(PKG_NAME)-$(PKG_VERSION)
PKG_SOURCE_VERSION:=4d7b8681700b084fb7dc6829f337b5818c8cbfbf
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION)-$(PKG_SOURCE_VERSION).tar.gz

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/nls.mk
$(call include_mk, python-package.mk)

define Package/sysupgrade-image-server
    SECTION:=devel
    CATEGORY:=Development
    TITLE:=attended sysupgrade image server
    MAINTAINER:=Paul Spooren <paul@spooren.de>
    URL:=http://github.com/aparcar/gsoc17-attended-sysupgrade/
    DEPENDS:=+python3-pyodbc +make @x86_64 @LIBC_USE_GLIBC
endef

define Package/sysupgrade-image-server/description
   Build server to deliver OpenWrt/LEDE sysupgrade images
endef

define Package/sysupgrade-image-server/conffiles
/etc/config/sysupserv
endef

define Build/Compile
endef

define Package/sysupgrade-image-server/install
	$(INSTALL_DIR) $(1)$(PYTHON_PKG_DIR)/sysupgrade-image-server
	$(CP) $(PKG_BUILD_DIR)/update-server/*.py $(1)$(PYTHON_PKG_DIR)/sysupgrade-image-server/
	$(INSTALL_DIR) $(1)/etc/config
	find $(1) -name "*\.pyc" -o -name "*\.pyo" | xargs rm -f
endef


$(eval $(call BuildPackage,sysupgrade-image-server))
