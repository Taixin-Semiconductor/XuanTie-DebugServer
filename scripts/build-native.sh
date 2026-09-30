#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
if [ "$#" -ne 3 ]; then
    echo 'Usage: build-native.sh NEW_BUILD_DIR PINNED_ELFUSE_CHECKOUT LIBUSB_PREFIX' >&2
    exit 2
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
BUILD=$1
CHECKOUT=$2
LIBUSB=$3
PIN=5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb
[ ! -e "$BUILD" ] || { echo 'Build directory already exists; choose a new path.' >&2; exit 1; }
[ "$(git -C "$CHECKOUT" rev-parse HEAD)" = "$PIN" ] || { echo 'elfuse checkout is not at the release pin.' >&2; exit 1; }
[ -x /opt/homebrew/opt/binutils/bin/objcopy ] || { echo 'Homebrew binutils is required to build.' >&2; exit 1; }
mkdir -p "$BUILD/elfuse-source" "$BUILD/runtime/lib"
git -C "$CHECKOUT" archive "$PIN" > "$BUILD/elfuse-source.tar"
tar -xf "$BUILD/elfuse-source.tar" -C "$BUILD/elfuse-source"
git -C "$BUILD/elfuse-source" apply "$ROOT/macos/macos14-compat.patch"
(cd "$BUILD/elfuse-source" && PATH="/opt/homebrew/opt/binutils/bin:$PATH" \
    make -j8 elfuse EXTRA_CFLAGS=-mmacosx-version-min=14.4)
cp "$LIBUSB/lib/libusb-1.0.0.dylib" "$BUILD/runtime/lib/"
install_name_tool -id @rpath/libusb-1.0.0.dylib "$BUILD/runtime/lib/libusb-1.0.0.dylib"
clang -arch arm64 -mmacosx-version-min=14.4 -Wall -Wextra -Werror \
    -I"$LIBUSB/include/libusb-1.0" "$ROOT/macos/cklink-usb.c" \
    -L"$BUILD/runtime/lib" -lusb-1.0.0 \
    -Wl,-rpath,@executable_path/lib -o "$BUILD/runtime/cklink-usb"
codesign --force --sign - "$BUILD/runtime/lib/libusb-1.0.0.dylib"
codesign --force --sign - "$BUILD/runtime/cklink-usb"
codesign --verify "$BUILD/runtime/cklink-usb"
codesign --verify "$BUILD/elfuse-source/build/elfuse"
echo "Native runtime built in $BUILD"
