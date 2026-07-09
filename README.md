# XuanTie DebugServer

[简体中文](README.zh-CN.md)

Prebuilt XuanTie DebugServer packages for connecting GDB and other debug clients to XuanTie / C-SKY targets through supported debug probes.

This repository stores binary release archives for Linux x86_64 and Windows hosts. The Linux package includes `DebugServerConsole.elf`, shared libraries, Ck-Link firmware files, target-description XML files, and example client code.

## Repository Contents

| Archive | Host system | Contents | Notes | SHA256 |
| --- | --- | --- | --- | --- |
| `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.sh` | Linux x86_64 | Self-extracting installer | Prompts for install path; default path is `/usr/bin/XUANTIE_DebugServer`; installs a `DebugServerConsole` wrapper | `4B6BBF438E271FA612DA09E17C53155478A35E27EF3175E132127D11712D9EC5` |
| `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz` | Linux x86_64 | Direct `XUANTIE_DebugServer/` package tree | Extracted from the `.sh` payload for manual installs without installer prompts | `226C930FA42BDE56387E04945EC3A4CA9BFA70117D485971C8E9B06DCA7B6A51` |
| `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.sh.tar.gz` | Linux x86_64 | Compressed copy of the `.sh` installer | Contains one file: `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.sh` | `24413810F02160E262A04CF22835ADADF061C120F5AD9A7A4B3F2C821A122194` |
| `XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip` | Windows | InstallShield installer bundle | Extract and run `setup.exe` | `588C5919441C9D6D5CFC18CAB2DB88147ACAB57ABBC06FDD437DBB6B6AC10C8F` |

The release version is `V5.18.10`. The release date is `20260603`, taken from the upstream package filenames.

## Linux Install

### Installer

```sh
chmod +x XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.sh
sudo ./XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.sh -i
```

The installer asks for an install path. If left blank, it uses `/usr/bin` and installs the package under `/usr/bin/XUANTIE_DebugServer`.

The installer also:

- writes `/etc/ld.so.conf.d/csky-debug.conf`
- runs `ldconfig`
- creates `/usr/bin/DebugServerConsole`

### Manual Tarball Install

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

If you installed with the `.sh` installer, use the wrapper command:

```sh
DebugServerConsole --help
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

When installed with the Linux `.sh` installer, the wrapper command is:

```sh
DebugServerConsole
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
- The direct Linux `.tar.gz` was repackaged from the `.sh` installer payload. It contains the same `XUANTIE_DebugServer/` package tree without running installer scripts.
- The Linux package contains Ck-Link firmware files under `links/Ck-Link/`.
- The Linux package includes libusb license files under `license/libusb/`.
- Some Linux systems may require udev rules or device permissions before a non-root user can access a USB debug probe.
- Check upstream licensing and redistribution terms before publishing modified or mirrored packages.
