#!/usr/bin/env python3
"""Prepare the canonical DebugServer macOS arm64 r2 archive from verified r1."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import stat
import subprocess
import tarfile
import tempfile


R1_NAME = "XuanTie-DebugServer-V5.18.10-macos-arm64-r1.tar.gz"
R1_SHA256 = "cfaf90556246cde0f2d11de045c6ee2472c0d2fbf0e02984c95504db11109445"
R1_PACKAGE = "XuanTie-DebugServer-V5.18.10-macos-arm64-r1"
R2_PACKAGE = "XuanTie-DebugServer-V5.18.10-macos-arm64-r2"
MANIFEST_NAME = "manifest.json"
SUMS_NAME = "SHA256SUMS"
HOST_ALIAS = "127.0.0.1 elfuse"


class PackageError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_name(name: str) -> str:
    if not name or "\\" in name or "\x00" in name or "\r" in name or "\n" in name:
        raise PackageError(f"unsafe archive path: {name!r}")
    clean = posixpath.normpath(name.rstrip("/"))
    if clean in ("", ".", "..") or clean.startswith("../") or clean.startswith("/"):
        raise PackageError(f"unsafe archive path: {name!r}")
    return clean


def safe_link(name: str, target: str, package_root: str) -> None:
    if not target or "\\" in target or "\x00" in target:
        raise PackageError(f"unsafe symlink target: {name} -> {target!r}")
    if name.startswith(package_root + "/sysroot/"):
        guest_root = package_root + "/sysroot"
        if target.startswith("/"):
            resolved = posixpath.normpath(guest_root + "/" + target.lstrip("/"))
        else:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        if resolved != guest_root and not resolved.startswith(guest_root + "/"):
            raise PackageError(f"guest symlink escapes sysroot: {name} -> {target}")
        return
    if target.startswith("/"):
        raise PackageError(f"host symlink is absolute: {name} -> {target}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    if resolved != package_root and not resolved.startswith(package_root + "/"):
        raise PackageError(f"package symlink escapes root: {name} -> {target}")


def real_parents(root: Path, destination: Path) -> None:
    current = root
    relative = destination.relative_to(root)
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise PackageError(f"archive path traverses symlink parent {current}")
        if current.exists() and not current.is_dir():
            raise PackageError(f"archive parent is not a directory: {current}")
        current.mkdir(exist_ok=True)


def safe_extract(archive_path: Path, destination: Path, expected_root: str) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 100_000:
            raise PackageError("DebugServer archive has too many entries")
        for member in members:
            name = safe_name(member.name)
            if name in seen:
                raise PackageError(f"duplicate archive entry: {name}")
            seen.add(name)
            if name != expected_root and not name.startswith(expected_root + "/"):
                raise PackageError(f"unexpected archive root: {name}")
            path = destination.joinpath(*PurePosixPath(name).parts)
            real_parents(destination, path)
            if member.isdir():
                if path.is_symlink():
                    raise PackageError(f"directory would replace a symlink: {name}")
                path.mkdir(exist_ok=True)
                os.chmod(path, member.mode & 0o7777)
            elif member.isreg():
                source = archive.extractfile(member)
                if source is None:
                    raise PackageError(f"cannot read archive member: {name}")
                with source, path.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                os.chmod(path, member.mode & 0o7777)
            elif member.issym():
                safe_link(name, member.linkname, expected_root)
                if path.exists() or path.is_symlink():
                    raise PackageError(f"symlink would replace an existing path: {name}")
                os.symlink(member.linkname, path)
            else:
                raise PackageError(f"unsupported archive member type: {name}")
    root = destination / expected_root
    if not root.is_dir() or root.is_symlink():
        raise PackageError(f"expected bundle directory {expected_root} is missing")
    return root


def inventory(root: Path, exclude_metadata: bool) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        dirs.sort()
        files.sort()
        names = list(dirs) + list(files)
        for name in names:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if exclude_metadata and relative in (MANIFEST_NAME, SUMS_NAME):
                continue
            info = path.lstat()
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                dirs[:] = [directory for directory in dirs if directory != name]
                target = os.readlink(path)
                entries.append({"path": relative, "type": "symlink", "mode": mode, "target": target,
                                "sha256": hashlib.sha256(os.fsencode(target)).hexdigest()})
            elif stat.S_ISDIR(info.st_mode):
                entries.append({"path": relative, "type": "directory", "mode": mode})
            elif stat.S_ISREG(info.st_mode):
                entries.append({"path": relative, "type": "file", "mode": mode, "sha256": sha256_file(path)})
            else:
                raise PackageError(f"unsupported special file: {relative}")
    entries.sort(key=lambda item: str(item["path"]))
    return entries


def write_integrity(root: Path) -> int:
    entries = inventory(root, True)
    manifest = {"schema_version": 1, "package": R2_PACKAGE, "entries": entries}
    (root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sums = [f"{entry['sha256']}  {entry['path']}" for entry in entries if entry["type"] == "file"]
    (root / SUMS_NAME).write_text("\n".join(sums) + "\n", encoding="ascii")
    return len(entries)


def verify_integrity(root: Path) -> int:
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("package") != R2_PACKAGE:
        raise PackageError("refreshed manifest identity is invalid")
    actual = inventory(root, True)
    if manifest.get("entries") != actual:
        raise PackageError("refreshed manifest does not match the bundle tree")
    checksums: dict[str, str] = {}
    for line in (root / SUMS_NAME).read_text(encoding="ascii").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64 or parts[1] in checksums:
            raise PackageError(f"invalid SHA256SUMS row: {line!r}")
        checksums[parts[1]] = parts[0]
    expected = {str(entry["path"]): str(entry["sha256"]) for entry in actual if entry["type"] == "file"}
    if checksums != expected:
        raise PackageError("SHA256SUMS does not match regular package files")
    return len(actual)


def verify_runtime(bundle: Path) -> None:
    executable = bundle / "bin" / "debugserver"
    try:
        doctor = subprocess.run(
            [str(executable), "doctor", "--offline"], cwd=bundle,
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PackageError(f"fresh bundle offline doctor could not run: {exc}") from exc
    if doctor.returncode != 0:
        detail = (doctor.stdout + doctor.stderr).strip()
        raise PackageError(f"fresh bundle offline doctor failed: {detail}")

    try:
        help_result = subprocess.run(
            [str(executable), "help"], cwd=bundle,
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PackageError(f"fresh bundle vendor help could not run: {exc}") from exc
    help_text = help_result.stdout + help_result.stderr
    if help_result.returncode != 255 or "XuanTie Debugger Server" not in help_text or "Usage" not in help_text:
        raise PackageError(
            "fresh bundle vendor help failed: "
            f"exit={help_result.returncode}, output={(help_text.strip())!r}"
        )


def prepare_tree(root: Path, source_name: str) -> int:
    if not root.name == R1_PACKAGE:
        raise PackageError(f"expected source directory {R1_PACKAGE}, got {root.name}")
    hosts = root / "sysroot" / "etc" / "hosts"
    if hosts.is_symlink() or not hosts.is_file():
        raise PackageError("r1 guest sysroot/etc/hosts is not a regular file")
    text = hosts.read_text(encoding="utf-8")
    alias_present = False
    for line in text.splitlines():
        fields = line.split("#", 1)[0].split()
        if fields and fields[0] == "127.0.0.1" and "elfuse" in fields[1:]:
            alias_present = True
            break
    if not alias_present:
        if text and not text.endswith("\n"):
            text += "\n"
        text += HOST_ALIAS + "\n"
        hosts.write_text(text, encoding="utf-8")

    readme = root / "README.md"
    if readme.is_symlink() or not readme.is_file():
        raise PackageError("r1 package README.md is not a regular file")
    first = readme.read_text(encoding="utf-8").splitlines()[0]
    if "macOS arm64 r1" not in first:
        raise PackageError("r1 README heading does not match the pinned release")
    readme.write_text(bundle_readme(source_name), encoding="utf-8")
    notes = (
        "# macOS arm64 r2 release notes\n\n"
        f"Derived from `{source_name}` (SHA-256 `{R1_SHA256}`).\n\n"
        "The guest sysroot now includes the mapping `127.0.0.1 elfuse` in "
        "`sysroot/etc/hosts`. The vendor executable, host launcher, native USB "
        "helper, elfuse runtime, and remaining binary payload are retained from r1.\n"
    )
    (root / "RELEASE-NOTES.md").write_text(notes, encoding="utf-8")

    renamed = root.parent / R2_PACKAGE
    root.rename(renamed)
    root = renamed
    count = write_integrity(root)
    verify_integrity(root)
    return count


def bundle_readme(source_name: str) -> str:
    return f"""# XuanTie DebugServer V5.18.10 — macOS arm64 r2

This bundle runs on native Apple Silicon with macOS 14.4 or newer and Apple's
Rosetta Linux runtime. Running it does not require Python, Homebrew, Docker,
Colima, or a virtual machine. The executables are ad hoc signed, with the
Hypervisor entitlement on elfuse; they are not Developer ID signed or notarized.

## Install and inspect

Extract the archive to a writable directory and keep its directory tree together.
Paths containing spaces are supported. Add its `bin` directory to `PATH` if desired.

```sh
cd {R2_PACKAGE}
./bin/debugserver doctor --offline
./bin/debugserver doctor
./bin/debugserver help
./bin/debugserver list
```

`doctor --offline` checks host compatibility, runtime signatures, Hypervisor
entitlement, and file SHA-256 sums. `doctor` also inspects USB identities and
configurations without selecting a configuration or claiming an interface.
Guest help prints vendor help and preserves its exit status (V5.18.10 normally
returns 255). `list` passes only `-list-ice` to DebugServer. These commands never
activate a loader automatically. Logs go to stdout/stderr; redirect them to
files when recording a test.

## CK-Link loader activation and reconnect

If `doctor` reports loader **c510:b211, configuration 0**, explicitly run:

```sh
./bin/debugserver activate
# When several loaders are connected, select the serial reported by doctor:
./bin/debugserver activate --serial YOUR_PROBE_SERIAL
```

This sends one standard `SET_CONFIGURATION(1)` to the selected loader. It changes
USB state; it sends no firmware data or target commands. The helper refuses
ambiguous selection and refuses a loader already at a nonzero configuration.
Failures are reported without automatic retries. Then wait for normal mode
**32bf:b210**, allow the accessory in macOS, and run `doctor` and `list` again.
Activation alone does not prove the normal-mode transition succeeded.

If the Mac retains a stale loader session, unplug the Mac-side adapter/hub and
disconnect the probe's target cable so the probe loses power completely.
Reconnect probe USB first, inspect its mode, activate only if needed, and allow
the accessory in macOS. Reconnect the target once the probe appears IDLE. The
experimental `USBDeviceReEnumerate` reset patch is not included; it did not fix
target access in the earlier comparison. The launcher disables inherited
diagnostic environment switches.

## Target check and vendor options

For intentional diagnosis of a powered CK803SG board, 2-wire at requested
2500 kHz:

```sh
./bin/debugserver check
./bin/debugserver check --serial YOUR_PROBE_SERIAL
```

`check` requires exactly one normal-mode CK-Link and no loaders. It enters target
debug mode and reads/writes debug registers, including GPRs; previous target
execution state is not preserved or verified. Its fixed arguments are
`-arch csky -setcdi 2 -setclk 2500k -check-target -skip-enter --debug connect`.
Use it only when intentionally diagnosing that connected board.

`debugserver run [vendor options...]` and `bin/DebugServerConsole.elf [options...]`
forward options to the vendor executable using elfuse's default watchdog settings.
Guest working directory and shared-library paths resolve within the bundle. The
launcher passes `no` then EOF to stdin, declining ordinary firmware-update
prompts and keeping invocation noninteractive; explicit vendor options still
have their documented effects. Server exit codes and stdout/stderr are retained.

## r2 change and validation limits

This archive is derived from checksum-verified `{source_name}` (SHA-256
`{R1_SHA256}`). It adds `127.0.0.1 elfuse` to the guest `sysroot/etc/hosts` so
elfuse guest hostname lookup resolves `elfuse`. The vendor executable, launcher,
native USB helper, elfuse runtime, and other binary payload are retained from r1.

A separate source prototype on macOS 14.8.7 arm64 with CK-Link `58D8` (app 2.32)
completed live CK803SG register/stack inspection and one hardware-breakpoint
instruction step. That test used prototype sources and temporary guest files;
it is separate evidence and does not validate this archived r2 bundle against
hardware. This archive has passed fresh extraction, manifest/SHA256SUMS checks,
offline readiness and vendor-help checks. Physical use of the packaged r2
binaries, probe activation, GDB sessions, flashing, another Mac, and general
probe compatibility have not been validated for this archive.

The earlier V5.18.10 target check used a different elfuse binary and one working
app 2.32 probe; a second app 2.36 probe returned zero target values on macOS and
an Ubuntu Linux VM. The failure followed the physical probe; firmware causation
was not established. The vendor archive SHA-256 is
`226c930fa42bde56387e04945ec3a4ca9bfa70117d485971c8e9b06dca7b6a51`; the vendor
executable SHA-256 is `39d5d35269c4566be267b4e0a66a05c17e46ab7512bcb142811b5e9c21ae52ba`.
elfuse source pin: `5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb`.

## Provenance and integrity

`manifest.json` records file hashes, modes, and symlink targets; `SHA256SUMS`
verifies regular files. `python3 tools/verify-package.py .` checks the full
manifest, including links and extra files. The runtime itself does not use
Python. elfuse is Apache-2.0; native libusb is LGPL-2.1-or-later; the guest
sysroot and vendor files retain their own copyright and license notices. The
libusb source archive is included for rebuilding or replacing its dynamic library.

Relevant upstream sources: [elfuse](https://github.com/sysprog21/elfuse),
[libusb](https://github.com/libusb/libusb), [vendor archive repository]
(https://github.com/Taixin-Semiconductor/XuanTie-DebugServer).
"""


def create_archive(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open("xb") as raw:
            created = True
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as zipped:
                with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.GNU_FORMAT) as archive:
                    paths: list[Path] = []
                    for current, dirs, files in os.walk(root.parent, topdown=True, followlinks=False):
                        base = Path(current)
                        dirs.sort()
                        files.sort()
                        for name in list(dirs):
                            item = base / name
                            paths.append(item)
                            if item.is_symlink():
                                dirs.remove(name)
                        paths.extend(base / name for name in files)
                    paths.sort(key=lambda item: item.relative_to(root.parent).as_posix())
                    for path in paths:
                        relative = path.relative_to(root.parent).as_posix()
                        info = path.lstat()
                        name = relative + ("/" if stat.S_ISDIR(info.st_mode) else "")
                        header = tarfile.TarInfo(name)
                        header.uid = header.gid = 0
                        header.uname = header.gname = ""
                        header.mtime = 0
                        header.mode = stat.S_IMODE(info.st_mode)
                        if stat.S_ISDIR(info.st_mode):
                            header.type = tarfile.DIRTYPE
                            archive.addfile(header)
                        elif stat.S_ISLNK(info.st_mode):
                            header.type = tarfile.SYMTYPE
                            header.linkname = os.readlink(path)
                            archive.addfile(header)
                        elif stat.S_ISREG(info.st_mode):
                            header.type = tarfile.REGTYPE
                            header.size = info.st_size
                            with path.open("rb") as stream:
                                archive.addfile(header, stream)
                        else:
                            raise PackageError(f"unsupported special package path: {relative}")
    except FileExistsError as exc:
        raise PackageError(f"output already exists: {output}") from exc
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-archive", type=Path, required=True, help="checksum-pinned DebugServer r1 archive")
    parser.add_argument("--output", type=Path, required=True, help="canonical r2 tar.gz output path")
    args = parser.parse_args()
    actual = sha256_file(args.r1_archive)
    if actual != R1_SHA256:
        raise PackageError(f"r1 archive SHA-256 mismatch: {actual}")

    output = args.output.resolve()
    if output.name != R2_PACKAGE + ".tar.gz":
        raise PackageError(f"--output must be named {R2_PACKAGE}.tar.gz")

    with tempfile.TemporaryDirectory(prefix="sdktools-debugserver-r2-") as temporary:
        stage = Path(temporary)
        root = safe_extract(args.r1_archive, stage / "source", R1_PACKAGE)
        count = prepare_tree(root, args.r1_archive.name)
        prepared_root = root.parent / R2_PACKAGE
        created_output = False
        try:
            create_archive(prepared_root, output)
            created_output = True
            with tempfile.TemporaryDirectory(prefix="sdktools-debugserver-r2-fresh-") as verify_dir:
                fresh_root = safe_extract(output, Path(verify_dir) / "unpacked", R2_PACKAGE)
                fresh_count = verify_integrity(fresh_root)
                if fresh_count != count:
                    raise PackageError("fresh archive extraction has a different manifest entry count")
                if HOST_ALIAS not in (fresh_root / "sysroot/etc/hosts").read_text(encoding="utf-8"):
                    raise PackageError("fresh archive is missing the guest hostname alias")
                verify_runtime(fresh_root)
                if verify_integrity(fresh_root) != fresh_count:
                    raise PackageError("runtime smoke changed files in the fresh package")
        except Exception:
            if created_output:
                output.unlink(missing_ok=True)
            raise
        digest = sha256_file(output)
        print(f"archive: {output}")
        print(f"archive_sha256: {digest}")
        print(f"archive_bytes: {output.stat().st_size}")
        print(f"manifest_entries: {count}")
        print(f"fresh_manifest_entries: {fresh_count}")
        print(f"package_identity: {R2_PACKAGE}")
        print("offline_doctor: passed")
        print("vendor_help: passed (exit 255)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackageError as exc:
        raise SystemExit(f"package error: {exc}")
