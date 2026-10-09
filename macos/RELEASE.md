# macOS arm64 r2 release validation

Archive: XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz
Size: 38,882,767 bytes
SHA-256: baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30

The archive was prepared from the checksum-verified r1 archive
XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz (SHA-256
cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445). The r2
change adds 127.0.0.1 elfuse to sysroot/etc/hosts. The vendor executable,
launcher, native USB helper, elfuse runtime and other binary payload are
retained from r1.

## Validation

- The r1 source archive checksum was verified before extraction.
- Fresh r2 extraction passed the package manifest and SHA256SUMS checks:
  5,538 entries before packaging and 5,538 after extraction.
- The guest hostname mapping was checked in the fresh extraction.
- Offline doctor and vendor help passed on the fresh extraction; vendor help
  returned its expected exit status 255.
- The SDKTools preparation tests cover payload retention, the exact loopback
  mapping, integrity regeneration, safe extraction, checksum rejection and
  absence of an external checksum sidecar.

## Separate source-prototype evidence

A source prototype on macOS 14.8.7 arm64 with CK-Link Lite V2 app 2.32
(serial suffix 58D8) and a powered CK803SG completed GDB register, stack and
bounded memory inspection. A hardware breakpoint at main+2 (0x20005B42) was
hit by one instruction step from 0x20005B40. The breakpoint was removed and
GDB disconnected. This is source-prototype evidence and does not validate the
canonical r2 archive's packaged binaries against hardware.

Physical probe activation, hardware GDB use of the canonical r2 archive,
flashing, another Mac and general probe compatibility remain unvalidated. No
firmware or target operation was performed while preparing the archive.

## Rebuild

See [BUILD.md](BUILD.md). The package builder reports the archive SHA-256; the
repository READMEs record the release archive digest. Package-internal
manifest.json and SHA256SUMS cover files and symlinks inside the bundle.
