# XuanTie DebugServer

[简体中文](README.zh-CN.md)

Prebuilt XuanTie DebugServer packages for connecting GDB and other debug clients to XuanTie / C-SKY targets through supported debug probes.

This repository stores binary release archives for Linux x86_64 and Windows hosts. The Linux package includes `DebugServerConsole.elf`, shared libraries, Ck-Link firmware files, target-description XML files, and example client code.

## Repository Contents

| Archive | Host system | Contents | Notes | SHA256 |
| --- | --- | --- | --- | --- |
| `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz` | Linux x86_64 | Direct `XUANTIE_DebugServer/` package tree | Manual install package | `226C930FA42BDE56387E04945EC3A4CA9BFA70117D485971C8E9B06DCA7B6A51` |
| `XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip` | Windows | InstallShield installer bundle | Extract and run `setup.exe` | `588C5919441C9D6D5CFC18CAB2DB88147ACAB57ABBC06FDD437DBB6B6AC10C8F` |

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
