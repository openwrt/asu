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
PKG_SOURCE_VERSION:=68cab3454c676894ac3c0f9344d190089ecac7e8
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION)-$(PKG_SOURCE_VERSION).tar.gz

include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/nls.mk
$(call include_mk, python3-package.mk)

define Package/sysupgrade-image-server
    SECTION:=devel
    CATEGORY:=Development
    TITLE:=attended sysupgrade image server
    MAINTAINER:=Paul Spooren <paul@spooren.de>
    URL:=http://github.com/aparcar/gsoc17-attended-sysupgrade/
    DEPENDS:=@x86_64 +bash +bzip2 +coreutils +coreutils-stat +diffutils +file \
             +gawk +gcc +getopt +git +libncurses +make +patch +perl \
             +perlbase-attributes +perlbase-findbin +perlbase-getopt \
             +perlbase-thread +python-light +tar +unzip +wget +xz +xzdiff \
             +xzgrep +xzless +xz-utils +zlib-dev \
             +psqlodbcw +curl +nginx +python3-flask +python3-pyodbc \
             +python3-yaml
    USERID:=upimaged:upimaged
endef

define Package/sysupgrade-image-server/description
   Build server to deliver OpenWrt/LEDE sysupgrade images
endef

define Package/sysupgrade-image-server/conffiles
/etc/config/upimaged
endef

define Build/Compile
endef

define Package/sysupgrade-image-server/install
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server
	$(CP) $(PKG_BUILD_DIR)/update-server/*.py $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server/
	$(CP) $(PKG_BUILD_DIR)/update-server/config.yml.default $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server/
	$(CP) $(PKG_BUILD_DIR)/update-server/imagebuilder-add-package_list-function.patch $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server/
	$(CP) $(PKG_BUILD_DIR)/update-server/distributions $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server/
	$(CP) $(PKG_BUILD_DIR)/update-server/tests $(1)$(PYTHON3_PKG_DIR)/sysupgrade-image-server/

	$(INSTALL_DIR) $(1)/usr/share/upimaged/
	$(CP) $(PKG_BUILD_DIR)/update-server/*.sql $(1)/usr/share/upimaged/

	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/upimaged.defaults $(1)/etc/uci-defaults/50-upimaged

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/upimaged.init $(1)/etc/init.d/upimaged

	find $(1) -name "*\.pyc" -o -name "*\.pyo" | xargs rm -f
endef


$(eval $(call BuildPackage,sysupgrade-image-server))
