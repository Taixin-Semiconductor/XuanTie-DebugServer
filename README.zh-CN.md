# 玄铁 DebugServer

[English](README.md)

本仓库保存玄铁 DebugServer 预编译二进制包，用于让 GDB 或其他调试客户端通过支持的调试器连接玄铁 / C-SKY 目标芯片。

Git 中保存打包源码、测试、文档及发布校验值。Linux x86_64、Windows 和 macOS arm64 压缩包通过固定版本的 [GitHub Release 附件](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/tag/debugserver-v5.18.10-r2)提供；克隆仓库不会下载二进制压缩包。Linux 包中包含 `DebugServerConsole.elf`、共享库、Ck-Link 固件文件、目标描述 XML 文件以及示例客户端代码。

## 发布下载

| 压缩包 | 主机系统 | 内容 | 说明 | SHA256 |
| --- | --- | --- | --- | --- |
| [`XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-linux-x86_64-V5.18.10-20260603.tar.gz) | Linux x86_64 | 直接可解压的 `XUANTIE_DebugServer/` 目录树 | 手动安装包 | `226C930FA42BDE56387E04945EC3A4CA9BFA70117D485971C8E9B06DCA7B6A51` |
| [`XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-windows-V5.18.10-20260603-2008.zip) | Windows | InstallShield 安装包 | 解压后运行 `setup.exe` | `588C5919441C9D6D5CFC18CAB2DB88147ACAB57ABBC06FDD437DBB6B6AC10C8F` |
| [`XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz) | macOS arm64 14.4+ | elfuse、Linux 运行库、厂商程序、原生 USB 工具 | 保留为 r1 源压缩包 | `cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445` |
| [`XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz`](https://github.com/Taixin-Semiconductor/XuanTie-DebugServer/releases/download/debugserver-v5.18.10-r2/XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz) | macOS arm64 14.4+ | elfuse、Linux 运行库、厂商程序、原生 USB 工具 | 规范客体主机名映射包；需要 Rosetta | `baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30` |

请先通过上表链接下载所需主机包，核对 SHA-256 后再按下方步骤安装。[SHA256SUMS](SHA256SUMS) 保存所有附件摘要；发布流程见 [RELEASES.md](RELEASES.md)。

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

## macOS arm64 r2

先将压缩包 SHA-256 与“发布下载”表中的值核对，再解压并运行离线检查：

~~~sh
printf '%s  %s\n' \
  'baad7202b980eeff48d33a84f0a8a1758c3dbb3a9fd3eff5a41b1a5879474c30' \
  'XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz' | shasum -a 256 -c -
tar -xzf XuanTie-DebugServer-V5.18.10-macos-arm64-r2.tar.gz
./XuanTie-DebugServer-V5.18.10-macos-arm64-r2/bin/debugserver doctor --offline
~~~

压缩包包含 elfuse、Debian amd64 运行库、厂商程序和原生 USB 工具。运行时需要
Apple Rosetta，不需要 Homebrew、Python、Docker 或虚拟机。r2 客体 sysroot 在
sysroot/etc/hosts 中将 elfuse 映射到 127.0.0.1；厂商程序、启动器、原生 USB
工具和 elfuse 运行时均沿用 r1。

单独的源码原型已使用 CK-Link Lite V2 app 2.32 完成 CK803SG GDB 寄存器和栈
检查，以及一次硬件断点单指令步进。这是原型验证，不代表 r2 规范压缩包
通过了硬件验证。压缩包已通过全新解压、manifest 和 SHA256SUMS 检查、离线就绪
检查以及厂商帮助输出检查。该 r2 压缩包尚未通过实体探针激活、硬件 GDB、
烧录、其他 Mac 或通用探针兼容性验证。详见[Mac 使用说明与验证范围](macos/README.md)
和[重新构建步骤](macos/BUILD.md)。

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
