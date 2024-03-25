#!/bin/sh

for config in $(grep '#' /builder/.config_local | awk '{print $2}'); do sed -i 's/'${config}'.*//' /builder/.config ; done;

cat /builder/.config_local >> /builder/.config