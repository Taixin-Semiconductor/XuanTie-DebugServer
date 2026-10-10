# XuanTie DebugServer

[简体中文](README.zh-CN.md)

Prebuilt XuanTie DebugServer packages for connecting GDB and other debug clients to XuanTie / C-SKY targets through supported debug probes.

This repository keeps packaging sources, tests, documentation, and release checksums in Git. Binary archives for Linux x86_64, Windows, and macOS arm64 are hosted as versioned [GitHub Release assets](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/tag/untagged-2e0e0fc50c0c16a8970e); cloning the repository does not download them. The Linux package includes `DebugServerConsole.elf`, shared libraries, Ck-Link firmware files, target-description XML files, and example client code.

## Release Downloads

| Archive | Host system | Contents | Notes | SHA256 |
| --- | --- | --- | --- | --- |
| [`XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/untagged-2e0e0fc50c0c16a8970e/XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz) | Linux x86_64 | Direct `XUANTIE_DebugServer/` package tree | Manual install package | `226C930FA42BDE56387E04945EC3A4CA9BFA70117D485971C8E9B06DCA7B6A51` |
| [`XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/untagged-2e0e0fc50c0c16a8970e/XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip) | Windows | InstallShield installer bundle | Extract and run `setup.exe` | `588C5919441C9D6D5CFC18CAB2DB88147ACAB57ABBC06FDD437DBB6B6AC10C8F` |
| [`XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/untagged-2e0e0fc50c0c16a8970e/XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz) | macOS arm64 14.4+ | elfuse, guest sysroot, vendor payload, native USB helper | Retained as the r1 source archive | `cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445` |
| [`XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/untagged-2e0e0fc50c0c16a8970e/XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz) | macOS arm64 14.4+ | elfuse, guest sysroot, vendor payload, native USB helper | Canonical bundle with guest hostname mapping; Rosetta required | `baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30` |

Download the archive for your host using the links above and verify its SHA-256 before following the install steps. [SHA256SUMS](SHA256SUMS) records every asset digest. See [release maintenance](RELEASES.md) for the publishing workflow.

The release version is `V5.18.10`. The release date is `20260603`, taken from the upstream package filenames.

## Linux Install

```sh
mkdir -p "$HOME/opt"
tar -xzf XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz -C "$HOME/opt"
export PATH="$HOME/opt/XUANTIE_DebugServer:$PATH"
export LD_LIBRARY_PATH="$HOME/opt/XUANTIE_DebugServer:${LD_LIBRARY_PATH:-}"
```

To make the environment changes persistent, add the `export PATH=...` and `export LD_LIBRARY_PATH=...` lines to your shell profile, such as `~/.bashrc` or `~/.profile`.

Verify the executable:

```sh
DebugServerConsole.elf --help
```

## Windows Install

From PowerShell:

```powershell
Expand-Archive .\XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip -DestinationPath .\xuantiedebugserver-installer
.\xuantiedebugserver-installer\XuanTie-DebugServer-windows-V5.18.10-20260603-2008\setup.exe
```

Follow the installer prompts. After installation, add the installed DebugServer directory to the Windows user or system `Path` environment variable if the installer does not do it automatically.

## macOS arm64 r2

Verify the archive against the SHA-256 shown in the Release Downloads table,
then extract and run its offline readiness check:

~~~sh
printf '%s  %s\n' \
  'baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30' \
  'XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz' | shasum -a 256 -c -
tar -xzf XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz
./XuanTie-DebugServer-V5.18.10-macos-arm64-r2/bin/debugserver doctor --offline
~~~

The bundle includes elfuse, Debian amd64 libraries, the vendor payload and a
native USB helper. It requires Apple's Rosetta runtime, but no Homebrew, Python,
Docker or virtual machine to run. The r2 guest sysroot maps elfuse to
127.0.0.1 in sysroot/etc/hosts; the vendor executable, launcher, native USB
helper and elfuse runtime are retained from r1.

A separate source prototype completed CK803SG GDB register/stack inspection and
one hardware-breakpoint instruction step with CK-Link Lite V2 app 2.32. This is
prototype evidence, not hardware validation of the canonical r2 archive. The
archive passed fresh extraction, manifest and SHA256SUMS checks, offline
readiness and vendor-help checks. Physical use of the packaged r2 binaries,
probe activation, flashing, another Mac and general probe compatibility have
not been validated for this archive. See [Mac usage and proof limits](macos/README.md)
and [rebuild instructions](macos/BUILD.md).

## Basic Usage

On Linux, the primary executable is:

```sh
DebugServerConsole.elf
```

Typical debug flows start DebugServer first, then connect to it from a GDB client supplied by the matching XuanTie / C-SKY toolchain.

## Included Target Descriptions

The Linux package includes target-description XML files for these families:

- `c_series`
- `ck801`
- `ck802`
- `ck803`
- `ck804`
- `ck805`
- `ck807`
- `ck810`
- `ck610`
- `ck860`
- `e_series`
- `i_series`
- `r_series`
- `riscv`
- `s_series`

Select the target, probe, and DebugServer options required by your chip, board, SDK, and GDB setup.

## Notes

- These are prebuilt binary packages, not source packages.
- The Linux `.tar.gz` contains the `XUANTIE_DebugServer/` package tree for manual installation.
- The Linux package contains Ck-Link firmware files under `links/Ck-Link/`.
- The Linux package includes libusb license files under `license/libusb/`.
- Some Linux systems may require udev rules or device permissions before a non-root user can access a USB debug probe.
- Check upstream licensing and redistribution terms before publishing modified or mirrored packages.
