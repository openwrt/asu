set -e

# the inputs:
TARGET="${TARGET:-x86/64}"
VERSION_PATH="${VERSION_PATH:-snapshots}"
UPSTREAM_URL="${UPSTREAM_URL:-http://downloads.openwrt.org}"

# use "*.Linux-x86_64.*" to create the imagebuilder
DOWNLOAD_FILE="imagebuilder-.*x86_64.tar.[xz|zst]"
DOWNLOAD_PATH="$VERSION_PATH/targets/$TARGET"

curl 'https://git.openwrt.org/?p=keyring.git;a=blob_plain;f=gpg/626471F1.asc' | gpg --import \
    && gpg --fingerprint --with-colons '<pgpsign-snapshots@openwrt.org>' | grep '^fpr:::::::::54CC74307A2C6DC9CE618269CD84BCED626471F1:$' \
    && echo '54CC74307A2C6DC9CE618269CD84BCED626471F1:6:' | gpg --import-ownertrust

wget "$UPSTREAM_URL/$DOWNLOAD_PATH/sha256sums" -O sha256sums
wget "$UPSTREAM_URL/$DOWNLOAD_PATH/sha256sums.asc" -O sha256sums.asc

gpg --with-fingerprint --verify sha256sums.asc sha256sums

# determine archive name
file_name="$(grep "$DOWNLOAD_FILE" sha256sums | cut -d "*" -f 2)"

# download imagebuilder/sdk archive
wget "$UPSTREAM_URL/$DOWNLOAD_PATH/$file_name"

# shrink checksum file to single desired file and verify downloaded archive
grep "$file_name" sha256sums > sha256sums_min
cat sha256sums_min
sha256sum -c sha256sums_min

# cleanup
rm -vrf sha256sums{,_min,.asc} keys/

tar xf "$file_name" --strip=1 --no-same-owner -C .
rm -vrf "$file_name"
