# Rebuild the macOS arm64 bundle

## Reproduce the canonical r2 archive

The canonical r2 archive is derived from the r1 release asset whose
SHA-256 is recorded in the Release Downloads table. From the repository
root, use the self-contained helper in this repository:

~~~sh
curl -fL https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz \
  -o XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz
python3 scripts/prepare-debugserver-r2.py \
  --r1-archive XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz \
  --output /tmp/XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz
shasum -a 256 /tmp/XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz
~~~

The helper verifies the pinned r1 archive SHA-256, adds 127.0.0.1 elfuse to
sysroot/etc/hosts, preserves the binary payload, writes the r2 README and
RELEASE-NOTES.md, regenerates manifest.json and SHA256SUMS, then freshly
extracts the archive and verifies integrity, offline doctor and vendor help.
The output path must not already exist. The r1 release asset is the exact
input for reproducing the canonical r2 digest.

Run the focused tests from the repository root:

~~~sh
python3 -m unittest scripts.test_package_macos scripts.test_prepare_debugserver_r2 -v
~~~

## Build a new r1 base bundle from source

This is a separate source-build workflow. A newly built r1 archive will usually
have a different digest and is not accepted by the pinned r2 helper until that
new input is reviewed and the helper's r1 SHA-256 pin is deliberately updated.
Do not substitute a new r1 build when reproducing the canonical r2 archive.

Build prerequisites: native Apple Silicon macOS 14.4+, Xcode command line
tools, Python 3, Git, Homebrew binutils and libusb 1.0.30. The r1 source package
uses the existing tested Debian sysroot at
../csky-gcc-build/elfuse-debugserver-poc/sysroot. Its image digest and installed
package versions are checked and recorded; running apt today does not reproduce
that frozen input.

From the repository root, choose new build/output directories:

~~~sh
curl -fL https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz \
  -o XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz
git clone https://github.com/sysprog21/elfuse.git /tmp/debugserver-elfuse
git -C /tmp/debugserver-elfuse switch --detach 5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb
sh scripts/build-native.sh /tmp/debugserver-build /tmp/debugserver-elfuse /opt/homebrew/opt/libusb
curl -fL https://github.com/libusb/libusb/releases/download/v1.0.30/libusb-1.0.30.tar.bz2 -o /tmp/libusb-1.0.30.tar.bz2
python3 scripts/package-macos.py \
  --elfuse-source /tmp/debugserver-build/elfuse-source \
  --sysroot ../csky-gcc-build/elfuse-debugserver-poc/sysroot \
  --vendor-archive XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz \
  --usb-helper /tmp/debugserver-build/runtime/cklink-usb \
  --libusb /tmp/debugserver-build/runtime/lib/libusb-1.0.0.dylib \
  --libusb-source-archive /tmp/libusb-1.0.30.tar.bz2 \
  --output /tmp/XuanTie-DebugServer-V5.18.10-macos-arm64-r1
~~~

This creates a new r1 base archive and prints its SHA-256. It does not produce
the canonical r2 archive by itself. Hardware activation and target validation
are separate actions; the offline r2 helper does not access USB devices.
