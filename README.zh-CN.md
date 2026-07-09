# 玄铁 DebugServer

[English](README.md)

本仓库保存玄铁 DebugServer 预编译二进制包，用于让 GDB 或其他调试客户端通过支持的调试器连接玄铁 / C-SKY 目标芯片。

本仓库包含 Linux x86_64 和 Windows 主机版发布包。Linux 包中包含 `DebugServerConsole.elf`、共享库、Ck-Link 固件文件、目标描述 XML 文件以及示例客户端代码。

## 仓库内容

| 压缩包 | 主机系统 | 内容 | 说明 | SHA256 |
| --- | --- | --- | --- | --- |
| `XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz` | Linux x86_64 | 直接可解压的 `XUANTIE_DebugServer/` 目录树 | 手动安装包 | `226C930FA42BDE56387E04945EC3A4CA9BFA70117D485971C8E9B06DCA7B6A51` |
| `XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip` | Windows | InstallShield 安装包 | 解压后运行 `setup.exe` | `588C5919441C9D6D5CFC18CAB2DB88147ACAB57ABBC06FDD437DBB6B6AC10C8F` |

发布版本为 `V5.18.10`。发布日期 `20260603` 来自上游包文件名。

## Linux 安装

```sh
mkdir -p "$HOME/opt"
tar -xzf XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz -C "$HOME/opt"
export PATH="$HOME/opt/XUANTIE_DebugServer:$PATH"
export LD_LIBRARY_PATH="$HOME/opt/XUANTIE_DebugServer:${LD_LIBRARY_PATH:-}"
```

如果需要永久生效，可以把 `export PATH=...` 和 `export LD_LIBRARY_PATH=...` 加入 `~/.bashrc` 或 `~/.profile`。

验证可执行文件：

```sh
DebugServerConsole.elf --help
```

## Windows 安装

在 PowerShell 中执行：

```powershell
Expand-Archive .\XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip -DestinationPath .\xuantiedebugserver-installer
.\xuantiedebugserver-installer\XuanTie-DebugServer-windows-V5.18.10-20260603-2008\setup.exe
```

随后按安装器提示操作。安装完成后，如果安装器没有自动配置环境变量，请将 DebugServer 安装目录加入 Windows 用户或系统 `Path` 环境变量。

## 基本用法

Linux 下主要可执行文件为：

```sh
DebugServerConsole.elf
```

常见调试流程是先启动 DebugServer，再使用匹配的玄铁 / C-SKY 工具链中的 GDB 客户端连接 DebugServer。

## 包含的目标描述

Linux 包内包含以下系列的目标描述 XML 文件：

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

请根据芯片、开发板、SDK 和 GDB 配置选择对应的目标、调试器和 DebugServer 参数。

## 注意事项

- 这些是预编译二进制包，不是源码包。
- Linux `.tar.gz` 包含用于手动安装的 `XUANTIE_DebugServer/` 目录树。
- Linux 包在 `links/Ck-Link/` 下包含 Ck-Link 固件文件。
- Linux 包在 `license/libusb/` 下包含 libusb 许可证文件。
- 某些 Linux 系统可能需要配置 udev 规则或设备权限，普通用户才能访问 USB 调试器。
- 发布修改版或镜像包前，请检查上游许可证和再分发条款。
