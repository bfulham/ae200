#!/bin/sh
set -eu

TARGET="${1:-/config/custom_components/ae200}"
SOURCE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/custom_components/ae200"

mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
cp -R "$SOURCE" "$TARGET"

echo "Installed Mitsubishi AE-200 integration to: $TARGET"
echo "Restart Home Assistant, then add Mitsubishi AE-200 from Devices & services."
