# XuanTie DebugServer V5.18.10 — macOS arm64 r1

Local offline CLI bundle, prepared 2026-09-30. Requires native Apple Silicon,
macOS 14.4 or newer, and Apple's installed Rosetta Linux runtime. Execution
does not require Python, Homebrew, Docker, Colima or a VM. The executables are
ad hoc signed, with the Hypervisor entitlement on elfuse; this release is not
Developer ID signed or notarized.

## Install and inspect

Extract the archive to a writable directory and keep its directory tree together.
Paths containing spaces are supported. Add its `bin` directory to `PATH` if desired.

```sh
cd XuanTie-DebugServer-V5.18.10-macos-arm64-r1
./bin/debugserver doctor --offline
./bin/debugserver doctor
./bin/debugserver help
./bin/debugserver list
```

`doctor --offline` checks host compatibility, runtime signatures, Hypervisor
entitlement and file SHA-256 sums. `doctor` also inspects USB identities and
current configurations without selecting a configuration or claiming an
interface. Guest help prints the vendor help and preserves its exit status
(V5.18.10 normally returns 255 for help). `list` passes only `-list-ice` to
DebugServer. They never activate a loader automatically. Logs go to stdout/stderr; redirect
them to files when recording a test.

## CK-Link loader activation and reconnect workaround

If `doctor` reports loader **c510:b211, configuration 0**, explicitly run:

```sh
./bin/debugserver activate
# When several loaders are connected, select the exact serial reported by doctor:
./bin/debugserver activate --serial YOUR_PROBE_SERIAL
```

This sends one standard `SET_CONFIGURATION(1)` to the selected loader. It
changes USB state; it sends no firmware data and no target commands. The helper
refuses ambiguous selection and refuses a loader already at a nonzero
configuration. Failures are reported without automatic retries. Afterward,
wait for normal mode **32bf:b210** and approve the macOS accessory prompt, then
run `doctor` and `list` again. Activation does not itself prove the normal-mode
transition succeeded.

If the Mac retains a stale loader session, unplug the Mac-side adapter/hub and
disconnect the probe's target cable so the probe loses power completely. Reconnect
probe USB first, inspect its mode, explicitly activate only if needed, and allow
the accessory in macOS. Reconnect the target once the probe appears IDLE. This
is the reconnect procedure used during the local tests.

The experimental `USBDeviceReEnumerate` reset patch is omitted. It re-enumerated
the failing probe twice but did not fix target access. This package uses elfuse's
normal USB handling. Inherited diagnostic environment switches are disabled by
the launcher.

## Target check and vendor options

For the tested powered CK803SG board, 2-wire at requested 2500 kHz:

```sh
./bin/debugserver check
./bin/debugserver check --serial YOUR_PROBE_SERIAL
```

`check` requires exactly one normal-mode CK-Link and no loaders. It enters target
debug mode and reads/writes debug registers, including GPRs; previous target
execution state is not preserved or verified. Its fixed arguments are
`-arch csky -setcdi 2 -setclk 2500k -check-target -skip-enter --debug connect`.
Use this only when intentionally diagnosing that connected board.

`debugserver run [vendor options...]` and `bin/DebugServerConsole.elf [options...]`
forward options to the vendor executable using elfuse's default watchdog settings. Guest
working directory and shared-library paths resolve within the bundle. The
launcher passes `no` then EOF to stdin, declining ordinary firmware-update
prompts and keeping invocation noninteractive; explicit vendor options still
have their documented effects. Server exit codes and stdout/stderr are retained.
There is no validated GDB session, breakpoint, stepping or flash workflow for
this release.

## Tested evidence and limits

On 2026-09-29, macOS 14.8.7 arm64 with pinned elfuse and DebugServer V5.18.10
listed the working CK-Link Lite V2 (app 2.32, serial suffix `58D8`) as IDLE and
passed the CK803SG target check with exit 0, HID `0x14039322`, DDCADDR readback
`0x000abcd0`, and CK803SG identification. The same board, flags and vendor binary
passed on an Ubuntu Linux VM with this probe. A second probe (app 2.36, serial
suffix `D8D8`) returned zero target values on both hosts. The failure follows
the physical probe; firmware causation is unproven.

That hardware-tested elfuse binary had optional trace/reset diagnostics compiled
in but disabled (SHA-256
`ebe7e078a6ebc7fc1308c4f82f0a1e814adb91cf5038e30b934d552d5df28d0b`).
This release builds the same pinned source with only the macOS compatibility
patch, omitting those experiments. Its new binary hash is in `manifest.json`.
Release validation covers a fresh extraction, guest dependency resolution,
vendor help, signature/entitlement verification, relocation and mocked USB
activation guards. The release binary and native activation helper have not
been retested against hardware. GDB, stepping, flashing, another Mac and general
probe compatibility remain untested.

The vendor archive SHA-256 is
`226c930fa42bde56387e04945ec3a4ca9bfa70117d485971c8e9b06dca7b6a51`;
the vendor executable SHA-256 is
`39d5d35269c4566be267b4e0a66a05c17e46ab7512bcb142811b5e9c21ae52ba`.
elfuse source pin: `5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb`.
Debian Bookworm amd64 base digest:
`sha256:f3034a6ec3c1205360777c4aae76234998866ad18806ae62b63a3f84ccad782b`;
installed package versions are recorded in `notices/provenance.json`.

## Provenance and local use

`manifest.json` records file hashes, modes and symlink targets;
`notices/provenance.json` records input provenance and installed package versions.
`SHA256SUMS` verifies regular files. For a full manifest check (including links
and extra files), a developer can run `python3 tools/verify-package.py .`.
The runtime itself does not use Python. Retain source and notices with the bundle:
elfuse is Apache-2.0; native libusb is LGPL-2.1-or-later; the guest sysroot and
vendor files retain their own copyright/license notices. The libusb source
archive is included for rebuilding/replacing its dynamically linked dylib.

This archive was assembled for local use from the repository's existing vendor
payload. Public redistribution of DebugServer and its firmware has not been
cleared. No public release was created.

Relevant upstream sources: [elfuse](https://github.com/sysprog21/elfuse),
[libusb](https://github.com/libusb/libusb),
[vendor archive repository](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer).
