# XuanTie DebugServer V5.18.10 — macOS arm64 r2

Archive: XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz

SHA-256: baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30

This bundle runs on native Apple Silicon with macOS 14.4 or newer and Apple's
Rosetta Linux runtime. Running it does not require Python, Homebrew, Docker,
Colima or a virtual machine. The executables are ad hoc signed, with the
Hypervisor entitlement on elfuse; they are not Developer ID signed or notarized.

## r2 package change

The archive is derived from the checksum-verified r1 archive
XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz (SHA-256
cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445). It adds
127.0.0.1 elfuse to the guest sysroot/etc/hosts so elfuse guest hostname lookup
resolves elfuse. The vendor executable, host launcher, native USB helper,
elfuse runtime and remaining binary payload are retained from r1.

## Install and inspect

Extract the archive to a writable directory and keep its directory tree together.
Paths containing spaces are supported. Add its bin directory to PATH if desired.

~~~sh
cd XuanTie-DebugServer-V5.18.10-macos-arm64-r2
./bin/debugserver doctor --offline
./bin/debugserver doctor
./bin/debugserver help
./bin/debugserver list
~~~

doctor --offline checks host compatibility, runtime signatures, Hypervisor
entitlement and file SHA-256 sums. doctor also inspects USB identities and
configurations without selecting a configuration or claiming an interface.
Guest help prints vendor help and preserves its exit status (V5.18.10 normally
returns 255). list passes only -list-ice to DebugServer. These commands never
activate a loader automatically. Logs go to stdout/stderr; redirect them to
files when recording a test.

## CK-Link loader activation and reconnect

If doctor reports loader c510:b211, configuration 0, explicitly run:

~~~sh
./bin/debugserver activate
# When several loaders are connected, select the serial reported by doctor:
./bin/debugserver activate --serial YOUR_PROBE_SERIAL
~~~

This sends one standard SET_CONFIGURATION(1) to the selected loader. It changes
USB state; it sends no firmware data or target commands. The helper refuses
ambiguous selection and refuses a loader already at a nonzero configuration.
Failures are reported without automatic retries. Then wait for normal mode
32bf:b210, allow the accessory in macOS, and run doctor and list again.
Activation alone does not prove the normal-mode transition succeeded.

If the Mac retains a stale loader session, unplug the Mac-side adapter/hub and
disconnect the probe's target cable so the probe loses power completely.
Reconnect probe USB first, inspect its mode, activate only if needed, and allow
the accessory in macOS. Reconnect the target once the probe appears IDLE. The
experimental USBDeviceReEnumerate reset patch is not included; it did not fix
target access in the earlier comparison. The launcher disables inherited
diagnostic environment switches.

## Target check and vendor options

For intentional diagnosis of a powered CK803SG board, 2-wire at requested
2500 kHz:

~~~sh
./bin/debugserver check
./bin/debugserver check --serial YOUR_PROBE_SERIAL
~~~

check requires exactly one normal-mode CK-Link and no loaders. It enters target
debug mode and reads/writes debug registers, including GPRs; previous target
execution state is not preserved or verified. Its fixed arguments are
-arch csky -setcdi 2 -setclk 2500k -check-target -skip-enter --debug connect.
Use it only when intentionally diagnosing that connected board.

debugserver run [vendor options...] and bin/DebugServerConsole.elf [options...]
forward options to the vendor executable using elfuse's default watchdog settings.
Guest working directory and shared-library paths resolve within the bundle. The
launcher passes no then EOF to stdin, declining ordinary firmware-update prompts
and keeping invocation noninteractive; explicit vendor options retain their
documented effects. Server exit codes and stdout/stderr are retained.

## Validation evidence and limits

The canonical r2 archive passed fresh extraction and verification of its
5,538-entry manifest and SHA256SUMS, offline doctor, and vendor help. The
vendor-help command returned its expected exit code 255. These checks did not
enumerate USB devices or access a probe or target.

A separate source prototype on macOS 14.8.7 arm64 with CK-Link Lite V2 app 2.32
(serial suffix 58D8) and a powered CK803SG completed GDB register, stack and
bounded memory inspection. A hardware breakpoint was set at main+2
(0x20005B42); one instruction step from 0x20005B40 hit it, then the breakpoint
was removed and GDB disconnected. This prototype result is separate evidence
and does not establish hardware validation of the canonical r2 archive.

The packaged r2 binaries have not been tested with physical probe activation,
GDB sessions, flashing or another Mac; general probe compatibility is also
unvalidated. The earlier V5.18.10 target check used a different elfuse binary
and one working app 2.32 probe. A second app 2.36 probe returned zero target
values on macOS and an Ubuntu Linux VM; the failure followed the physical probe,
but firmware causation was not established. No firmware or target operation was
performed while preparing the canonical r2 archive.

## Provenance and integrity

manifest.json records file hashes, modes and symlink targets; SHA256SUMS
verifies regular files. python3 tools/verify-package.py . checks the full
manifest, including links and extra files. The runtime itself does not use
Python. elfuse is Apache-2.0; native libusb is LGPL-2.1-or-later; the guest
sysroot and vendor files retain their own copyright and license notices. The
libusb source archive is included for rebuilding or replacing its dynamic library.
Check applicable upstream terms before redistributing vendor files.

Relevant upstream sources: [elfuse](https://github.com/sysprog21/elfuse),
[libusb](https://github.com/libusb/libusb), [vendor archive repository](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer).
