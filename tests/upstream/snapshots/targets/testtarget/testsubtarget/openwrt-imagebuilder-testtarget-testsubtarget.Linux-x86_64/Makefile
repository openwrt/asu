
image:
	mkdir -p $(BIN_DIR)/
	cp ./openwrt-testtarget-testsubtarget-testprofile-sysupgrade.bin $(BIN_DIR)/
	cp ./openwrt-testtarget-testsubtarget-testprofile.manifest $(BIN_DIR)/
	cp ./profiles.json $(BIN_DIR)/

manifest:
	@cat ./openwrt-testtarget-testsubtarget-testprofile.manifest

info:
	@cat ./openwrt-testtarget-testsubtarget-testprofile.info

val.KERNEL_BUILD_DIR:
	@echo "$$(pwd)/pseudo_kernel_build_dir/"
