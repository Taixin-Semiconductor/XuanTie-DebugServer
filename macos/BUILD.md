# Rebuild the local Mac bundle

Build prerequisites: native Apple Silicon macOS 14.4+, Xcode command line
tools, Python 3, Git, Homebrew binutils and libusb **1.0.30**. End users running
the resulting archive need only the host prerequisites in README.md.

The local first release uses the existing tested Debian sysroot at
`../csky-gcc-build/elfuse-debugserver-poc/sysroot`. Its image digest and installed
package versions are checked/recorded; this is a frozen input, not a claim that
running apt today reproduces the same packages. An extracted release sysroot
can also serve as that frozen input.

From the repository root, select new build/output directories:

```sh
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
```

The builder exports only the pinned Git tree, ignoring developer working-tree
changes, then applies `macos14-compat.patch` and builds/signs elfuse with its
Hypervisor entitlement. Native helper load paths use `@rpath`; the bundled
libusb install name is set before signing. `package-macos.py` verifies archive
hashes, installs the vendor payload afresh, preserves guest libraries/licenses,
records source/hashes and writes a `.tar.gz` plus adjacent `.sha256` file.

Before treating a new archive as tested, extract it to a different path,
verify the manifest, run `debugserver doctor --offline` and vendor help, and
inspect the guest loader's dependency list. Run the mock safety tests with
`python3 -m unittest discover -s macos/tests -v`. No mock test touches USB.
Hardware activation and target validation are separate, intentional actions.
