#!/bin/sh

tar czf openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64.tar.xz openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64/
sha256sum -b openwrt-imagebuilder-testtarget-testsubtarget.Linux-x86_64.tar.xz > sha256sums
usign -S -m sha256sums -s ../../../../../keys/testkey.sec
