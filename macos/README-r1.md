# XuanTie DebugServer V5.18.10 — macOS arm64 r1

This is the r1 base bundle for native Apple Silicon running macOS 14.4 or newer
with Apple's Rosetta Linux runtime. Running the bundle does not require Python,
Homebrew, Docker, Colima, or a virtual machine. The executables are ad hoc
signed, with the Hypervisor entitlement on elfuse; they are not Developer ID
signed or notarized.

The guest sysroot in r1 does not contain the mapping 127.0.0.1 elfuse in
sysroot/etc/hosts. Guest programs that resolve the elfuse hostname may fail
until that mapping is added.

## Install and inspect

Extract the archive to a writable directory and keep its directory tree
together. Paths containing spaces are supported.

~~~sh
cd XuanTie-DebugServer-V5.18.10-macos-arm64-r1
./bin/debugserver doctor --offline
./bin/debugserver help
~~~

doctor --offline checks host compatibility, runtime signatures, Hypervisor
entitlement, and file SHA-256 sums. Guest help prints vendor help and preserves
its exit status (V5.18.10 normally returns 255). These commands do not enumerate
USB devices or access a probe or target.

## Contents and integrity

The bundle contains elfuse, its guest sysroot, the XuanTie DebugServer V5.18.10
vendor payload, a native USB helper, source material, and license notices.
manifest.json records file hashes, modes, and symlink targets; SHA256SUMS
verifies regular files. python3 tools/verify-package.py . checks the complete
manifest. The runtime itself does not use Python.

elfuse is Apache-2.0; native libusb is LGPL-2.1-or-later; the guest sysroot and
vendor files retain their own copyright and license notices. Check applicable
upstream terms before redistributing vendor files.
