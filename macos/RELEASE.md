# Local release validation — 2026-09-30

Archive: `XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz`

Size: 39,049,517 bytes (about 37.2 MiB)

SHA-256: `cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445`

Clean elfuse source: `5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb`, with only
`macos14-compat.patch`. Release elfuse SHA-256:
`b541571f585127cb8c735c31952bd2e8072bab0d951cc9102167322204a9e461`.
Native USB helper and libusb 1.0.30 use relative load paths and ad hoc signatures.
elfuse has the Hypervisor entitlement. The archive includes the pinned vendor
payload, frozen Debian amd64 sysroot, source/license material and integrity metadata.

## Validation

- Native builds, code signatures and elfuse Hypervisor entitlement passed.
- 16 mocked USB guard and launcher tests passed; no physical USB calls occurred.
- 11 packaging/integrity tests passed, including archive traversal rejection,
  changed file/link/mode detection and pinned source/image checks.
- Eight final fresh-extraction checks passed in a path containing spaces:
  extraction, full manifest before execution, offline doctor, guest vendor help
  (its expected exit 255), guest loader dependencies, USB helper help, native
  library load paths and full manifest after execution.
- Independent release review approved the final archive and the 16 source files
  identified by fingerprint
  `3278363ef56ed51cde7c70f0fff30ae15f78a803dfbcdf6252f566bc7991d0c7`.
  The reviewer independently verified archive/tree equality and 5,537 manifest
  entries. A misleading wall-clock deadline claim was corrected; elfuse's timeout
  option is a vCPU watchdog, not a process execution deadline.

The final smoke report is [validation/smoke-result.json](validation/smoke-result.json).
Source fingerprints are in [validation/source-fingerprint.json](validation/source-fingerprint.json).
Commands can be reproduced with [BUILD.md](BUILD.md), the scripts and mock tests.

## Proof limits

The earlier working probe's CK803SG target check passed on macOS/elfuse and the
Linux VM. This clean release removes the optional trace/reset diagnostics from
that prior runtime. No release hardware activation or target retest was performed.
GDB, breakpoints, stepping, flashing, another Mac and general probe support remain
unvalidated. No USB configuration, reset, firmware write or target operation was
performed while assembling or smoke-testing this release.

This is a local archive. No commit, push or public release was made.
