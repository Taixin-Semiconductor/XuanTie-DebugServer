#!/usr/bin/env python3
"""Assemble an offline, relocatable macOS arm64 XuanTie DebugServer bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSION = "V5.18.10-macos-arm64-r1"
VENDOR_SHA256 = "226c930fa42bde56387e04945ec3a4ca9bfa70117d485971c8e9b06dca7b6a51"
LIBUSB_SOURCE_SHA256 = "fea36f34f9156400209595e300840767ab1a385ede1dc7ee893015aea9c6dbaf"
LIBUSB_SOURCE_VERSION = "1.0.30"
ELFUSE_COMMIT = "5027e21c0e8c49bfd54bfa6aec7c8b379e91d6fb"
ELFUSE_SOURCE_TREE_SHA256 = "c4ff3a405362a7008d457f9ef3566149d152e8f8a774b577af1c79e4c45b3bc8"
ELFUSE_PATCH_SHA256 = "c7aeda8960f3f6e440e528f1d7df8b79135dedefe654a8c9793f3c5f40d3ddc8"
DEBIAN_IMAGE = (
    "debian:bookworm@sha256:"
    "f3034a6ec3c1205360777c4aae76234998866ad18806ae62b63a3f84ccad782b"
)
MANIFEST_NAME = "manifest.json"
SUMS_NAME = "SHA256SUMS"
LIBUSB_SOURCE_URL = "https://github.com/libusb/libusb/releases/download/v{version}/libusb-{version}.tar.bz2"


class PackageError(Exception):
    """An input or package layout did not meet the release requirements."""


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_regular_file(path: Path, label: str, executable: bool = False) -> Path:
    if path.is_symlink() or not path.is_file():
        raise PackageError(f"{label} must be a regular file: {path}")
    if path.stat().st_size == 0:
        raise PackageError(f"{label} is empty: {path}")
    if executable and not path.stat().st_mode & 0o111:
        raise PackageError(f"{label} is not executable: {path}")
    return path


def _require_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise PackageError(f"{label} must be a directory: {path}")
    return path


def _copy_tree(
    source: Path,
    destination: Path,
    *,
    excluded_root_names: frozenset[str] = frozenset(),
    excluded_components: frozenset[str] = frozenset(),
) -> None:
    """Copy a tree without following links or accepting special files."""
    _require_directory(source, "source tree")
    destination.mkdir(parents=True, exist_ok=False)

    def copy_directory(src: Path, dst: Path, relative: PurePosixPath) -> None:
        entries = sorted(os.scandir(src), key=lambda entry: entry.name)
        for entry in entries:
            rel = relative / entry.name
            if len(rel.parts) == 1 and entry.name in excluded_root_names:
                continue
            if any(part in excluded_components for part in rel.parts):
                continue
            source_entry = Path(entry.path)
            target_entry = dst / entry.name
            info = entry.stat(follow_symlinks=False)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                os.symlink(os.readlink(source_entry), target_entry)
            elif stat.S_ISDIR(info.st_mode):
                target_entry.mkdir(mode=mode)
                copy_directory(source_entry, target_entry, rel)
                os.chmod(target_entry, mode)
                os.utime(target_entry, (info.st_atime, info.st_mtime), follow_symlinks=False)
            elif stat.S_ISREG(info.st_mode):
                shutil.copyfile(source_entry, target_entry, follow_symlinks=False)
                os.chmod(target_entry, mode)
                os.utime(target_entry, (info.st_atime, info.st_mtime), follow_symlinks=False)
            else:
                raise PackageError(f"unsupported special file in {source}: {rel}")

    root_info = source.stat()
    copy_directory(source, destination, PurePosixPath())
    os.chmod(destination, stat.S_IMODE(root_info.st_mode))
    os.utime(destination, (root_info.st_atime, root_info.st_mtime), follow_symlinks=False)


def _archive_relative_path(name: str) -> tuple[str, ...]:
    if "\\" in name or name.startswith("/"):
        raise PackageError(f"unsafe path in vendor archive: {name!r}")
    raw_parts = name.rstrip("/").split("/")
    if not raw_parts or raw_parts[0] != "XUANTIE_DebugServer":
        raise PackageError(f"unexpected top-level path in vendor archive: {name!r}")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise PackageError(f"unsafe path in vendor archive: {name!r}")
    return tuple(raw_parts[1:])


def _validate_link_target(relative: tuple[str, ...], target: str, label: str) -> None:
    if not target or target.startswith("/") or "\\" in target:
        raise PackageError(f"unsafe symlink in {label}: {target!r}")
    stack = list(relative[:-1])
    for component in target.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not stack:
                raise PackageError(f"symlink escapes extraction root in {label}: {target!r}")
            stack.pop()
        else:
            stack.append(component)


def safe_extract_vendor(archive_path: Path, destination: Path) -> None:
    """Extract only regular files, directories, and contained symlinks."""
    destination.mkdir(parents=True, exist_ok=False)
    try:
        archive = tarfile.open(archive_path, mode="r:*")
    except (tarfile.TarError, OSError) as exc:
        raise PackageError(f"cannot read vendor archive {archive_path}: {exc}") from exc

    with archive:
        members = archive.getmembers()
        paths: dict[tuple[str, ...], tarfile.TarInfo] = {}
        for member in members:
            relative = _archive_relative_path(member.name)
            if relative in paths:
                raise PackageError(f"duplicate path in vendor archive: {member.name}")
            if relative and not (member.isfile() or member.isdir() or member.issym()):
                raise PackageError(f"unsupported member type in vendor archive: {member.name}")
            if not relative and not member.isdir():
                raise PackageError("vendor archive root entry must be a directory")
            if member.issym():
                _validate_link_target(relative, member.linkname, member.name)
            paths[relative] = member

        for relative, member in paths.items():
            for length in range(1, len(relative)):
                parent = relative[:length]
                parent_member = paths.get(parent)
                if parent_member is not None and not parent_member.isdir():
                    raise PackageError(f"non-directory is a parent in vendor archive: {member.name}")

        directory_modes: list[tuple[Path, int, float]] = []

        def make_parents(relative: tuple[str, ...]) -> Path:
            current = destination
            for component in relative:
                current = current / component
                if current.is_symlink():
                    raise PackageError(f"symlink parent in vendor archive: {current}")
                if current.exists():
                    if not current.is_dir():
                        raise PackageError(f"non-directory parent in vendor archive: {current}")
                else:
                    current.mkdir(mode=0o755)
            return current

        for relative, member in paths.items():
            if not relative:
                directory_modes.append((destination, member.mode, member.mtime))
                continue
            parent = make_parents(relative[:-1])
            target = parent / relative[-1]
            if target.exists() or target.is_symlink():
                if member.isdir() and target.is_dir() and not target.is_symlink():
                    pass
                else:
                    raise PackageError(f"duplicate extraction target: {member.name}")
            if member.isdir():
                target.mkdir(mode=0o755, exist_ok=True)
                directory_modes.append((target, member.mode, member.mtime))
            elif member.issym():
                os.symlink(member.linkname, target)
            else:
                source_stream = archive.extractfile(member)
                if source_stream is None:
                    raise PackageError(f"cannot read regular file from vendor archive: {member.name}")
                with source_stream, target.open("xb") as output_stream:
                    shutil.copyfileobj(source_stream, output_stream, length=1024 * 1024)
                os.chmod(target, member.mode & 0o7777)
                os.utime(target, (member.mtime, member.mtime), follow_symlinks=False)

        for path, mode, mtime in reversed(directory_modes):
            os.chmod(path, mode & 0o7777)
            os.utime(path, (mtime, mtime), follow_symlinks=False)

    if not (destination / "DebugServerConsole.elf").is_file():
        raise PackageError("vendor archive does not contain DebugServerConsole.elf")


def _inventory(
    root: Path,
    *,
    exclude_metadata: bool = False,
    excluded_root_names: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def walk(directory: Path, relative: PurePosixPath) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            rel = relative / entry.name
            path_text = rel.as_posix()
            if len(rel.parts) == 1 and entry.name in excluded_root_names:
                continue
            if exclude_metadata and path_text in (MANIFEST_NAME, SUMS_NAME):
                continue
            info = entry.stat(follow_symlinks=False)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISDIR(info.st_mode):
                records.append({"path": path_text, "type": "directory", "mode": mode})
                walk(Path(entry.path), rel)
            elif stat.S_ISREG(info.st_mode):
                records.append({
                    "path": path_text,
                    "type": "file",
                    "mode": mode,
                    "sha256": hash_file(Path(entry.path)),
                })
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(entry.path)
                records.append({
                    "path": path_text,
                    "type": "symlink",
                    "mode": mode,
                    "target": target,
                    "sha256": hashlib.sha256(os.fsencode(target)).hexdigest(),
                })
            else:
                raise PackageError(f"unsupported special file in package: {path_text}")

    walk(root, PurePosixPath())
    records.sort(key=lambda item: item["path"])
    return records


def write_integrity_metadata(package_dir: Path, package_name: str) -> None:
    records = _inventory(package_dir, exclude_metadata=True)
    manifest = {
        "schema_version": 1,
        "package": package_name,
        "entries": records,
    }
    manifest_path = package_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"{record['sha256']}  {record['path']}"
        for record in records
        if record["type"] == "file"
    ]
    (package_dir / SUMS_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_libusb_version(library: Path, expected_source_version: str) -> tuple[str | None, str]:
    candidates = [library, library.resolve()]
    ancestors: set[Path] = set()
    for candidate in candidates:
        ancestors.update(candidate.parents)
    for ancestor in sorted(ancestors, key=lambda item: len(item.parts), reverse=True):
        if ancestor.parent.name == "libusb" and ancestor.parent.parent.name == "Cellar":
            return ancestor.name, f"Homebrew Cellar path {ancestor}"
        receipt = ancestor / "INSTALL_RECEIPT.json"
        if receipt.is_file():
            try:
                metadata = json.loads(receipt.read_text(encoding="utf-8"))
                source = metadata.get("source", {})
                versions = source.get("versions", {})
                version = versions.get("stable")
                if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version):
                    return version, f"{receipt}"
            except (OSError, json.JSONDecodeError):
                continue
    installed_receipt = Path("/opt/homebrew/opt/libusb/INSTALL_RECEIPT.json")
    if installed_receipt.is_file():
        try:
            metadata = json.loads(installed_receipt.read_text(encoding="utf-8"))
            source = metadata.get("source", {})
            version = source.get("versions", {}).get("stable")
            if version == expected_source_version and source.get("tap") == "homebrew/core":
                return version, f"{installed_receipt} paired with the pinned source archive"
        except (OSError, json.JSONDecodeError):
            pass
    return None, "version not exposed by the supplied library path or Homebrew receipt"


def _libusb_source_details(archive_path: Path) -> tuple[str, str, bytes]:
    try:
        archive = tarfile.open(archive_path, mode="r:*")
    except (tarfile.TarError, OSError) as exc:
        raise PackageError(f"cannot read libusb source archive {archive_path}: {exc}") from exc
    with archive:
        roots: set[str] = set()
        licenses: list[tarfile.TarInfo] = []
        for member in archive.getmembers():
            if "\\" in member.name or member.name.startswith("/"):
                raise PackageError(f"unsafe member in libusb source archive: {member.name!r}")
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] in (".", ".."):
                raise PackageError(f"unsafe member in libusb source archive: {member.name!r}")
            roots.add(parts[0])
            if len(parts) == 2 and parts[1] == "COPYING" and member.isfile():
                licenses.append(member)
        if len(roots) != 1:
            raise PackageError("libusb source archive must have one top-level directory")
        root_name = next(iter(roots))
        match = re.fullmatch(r"libusb-(\d+\.\d+\.\d+)", root_name)
        if not match:
            raise PackageError(f"unrecognized libusb source directory: {root_name}")
        if len(licenses) != 1:
            raise PackageError("libusb source archive must contain one top-level COPYING file")
        stream = archive.extractfile(licenses[0])
        if stream is None:
            raise PackageError("cannot read libusb COPYING file")
        with stream:
            license_text = stream.read()
        if b"GNU LESSER GENERAL PUBLIC LICENSE" not in license_text:
            raise PackageError("libusb COPYING file is not the expected LGPL text")
        return match.group(1), root_name, license_text


def _parse_dpkg_status(status_file: Path) -> list[dict[str, str]]:
    try:
        text = status_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackageError(f"cannot read dpkg status metadata: {exc}") from exc
    packages: list[dict[str, str]] = []
    for paragraph in re.split(r"\n\s*\n", text):
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if line and not line[0].isspace() and ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("Status", "").endswith(" installed"):
            packages.append({
                "package": fields.get("Package", ""),
                "version": fields.get("Version", ""),
                "architecture": fields.get("Architecture", ""),
                "status": fields["Status"],
            })
    packages.sort(key=lambda item: item["package"])
    return packages


def _git_revision(source: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return {
            "commit": ELFUSE_COMMIT,
            "verification": "packaging input is supplied as the pinned build source; .git metadata is absent",
            "git_metadata_present": False,
        }
    commit = result.stdout.strip()
    if commit != ELFUSE_COMMIT:
        raise PackageError(f"elfuse source is at {commit}, expected pinned commit {ELFUSE_COMMIT}")
    diff = subprocess.run(
        ["git", "-C", str(source), "diff", "--binary"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if diff.returncode != 0:
        raise PackageError("cannot inspect elfuse source diff")
    return {
        "commit": commit,
        "verification": "git HEAD checked",
        "git_metadata_present": True,
        "working_tree_diff_sha256": hashlib.sha256(diff.stdout).hexdigest(),
    }


def _directory_digest(root: Path, *, excluded_root_names: frozenset[str] = frozenset()) -> str:
    records = _inventory(root, excluded_root_names=excluded_root_names)
    encoded = json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_image_digest(sysroot: Path) -> str:
    digest_path = sysroot / "image.digest"
    try:
        recorded_image = digest_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise PackageError(f"cannot read sysroot image digest: {exc}") from exc
    if recorded_image != DEBIAN_IMAGE:
        raise PackageError(f"sysroot image digest mismatch: got {recorded_image!r}, expected {DEBIAN_IMAGE!r}")
    return recorded_image


def _ensure_guest_libusb_soname(directory: Path) -> Path:
    library = directory / "libusb-1.0.so"
    soname = directory / "libusb-1.0.so.0"
    if library.is_symlink() or not library.is_file():
        raise PackageError(f"vendor payload is missing libusb-1.0.so: {library}")
    if soname.is_symlink():
        if os.readlink(soname) == "libusb-1.0.so":
            return soname
        soname.unlink()
    elif os.path.lexists(soname):
        raise PackageError(f"vendor soname path must be a symlink: {soname}")
    os.symlink("libusb-1.0.so", soname)
    return soname


def _stage_usb_helper(
    compiled_helper: Path,
    helper_source: Path,
    runtime_directory: Path,
    source_directory: Path,
) -> None:
    _copy_file(compiled_helper, runtime_directory / "cklink-usb", mode=0o755)
    _copy_file(helper_source, source_directory / "cklink-usb.c")


def _load_verifier():
    verifier_path = REPO_ROOT / "scripts" / "verify-package.py"
    if not verifier_path.is_file():
        raise PackageError(f"missing package verifier: {verifier_path}")
    namespace: dict[str, Any] = {"__file__": str(verifier_path), "__name__": "_package_verifier"}
    exec(compile(verifier_path.read_bytes(), str(verifier_path), "exec"), namespace)
    return namespace["verify_package"]


def _copy_file(source: Path, target: Path, *, mode: int | None = None) -> None:
    _require_regular_file(source, source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target_mode = stat.S_IMODE(source.stat().st_mode) if mode is None else mode
    os.chmod(target, target_mode)
    shutil.copystat(source, target, follow_symlinks=False)
    if mode is not None:
        os.chmod(target, mode)


def _build_provenance(
    *,
    args: argparse.Namespace,
    package_dir: Path,
    vendor_hash: str,
    library_version: str | None,
    library_version_evidence: str,
    libusb_source_version: str,
    elfuse_revision: dict[str, Any],
    patch_hash: str,
    status_file: Path,
) -> dict[str, Any]:
    debian_version_path = args.sysroot / "etc" / "debian_version"
    debian_version = debian_version_path.read_text(encoding="utf-8").strip() if debian_version_path.is_file() else None
    elfuse_binary = package_dir / "runtime" / "elfuse"
    libusb_library = package_dir / "runtime" / "lib" / "libusb-1.0.0.dylib"
    return {
        "schema_version": 1,
        "release": args.version,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_vendor": {
            "archive": args.vendor_archive.name,
            "sha256": vendor_hash,
        },
        "elfuse": {
            **elfuse_revision,
            "compat_patch": "macos14-compat.patch",
            "compat_patch_sha256": patch_hash,
            "packaged_source_tree_sha256": _directory_digest(package_dir / "source" / "elfuse"),
            "source_tree_verification": "matches the pinned patched source inventory SHA-256",
            "runtime_build_sha256": hash_file(elfuse_binary),
        },
        "build_environment": {
            "container_image": DEBIAN_IMAGE,
            "image_digest": DEBIAN_IMAGE.split("@", 1)[1],
            "image_digest_file_sha256": hash_file(args.sysroot / "image.digest"),
            "debian_version": debian_version,
            "dpkg_status_sha256": hash_file(status_file),
            "installed_packages": _parse_dpkg_status(package_dir / "sysroot" / "var" / "lib" / "dpkg" / "status"),
        },
        "native_libusb": {
            "library": "runtime/lib/libusb-1.0.0.dylib",
            "library_sha256": hash_file(libusb_library),
            "version": library_version,
            "version_evidence": library_version_evidence,
            "origin": "Homebrew formula source archive; SHA-256 verified by package-macos.py",
            "source_archive": args.libusb_source_archive.name,
            "source_archive_sha256": hash_file(args.libusb_source_archive),
            "source_version": libusb_source_version,
            "source_url": LIBUSB_SOURCE_URL.format(version=libusb_source_version),
            "license": "LGPL-2.1-or-later text in notices/libusb-COPYING",
        },
    }


def package_readme_contents(template: str, package_name: str) -> str:
    match = re.fullmatch(r"XuanTie-DebugServer-(.+)-macos-arm64-(r1)", package_name)
    if match is None:
        raise PackageError("package-macos.py builds the r1 base bundle; derive r2 with the pinned r2 helper")
    version, identity = match.groups()
    _, separator, body = template.partition("\n")
    if not separator or not template.startswith("# XuanTie DebugServer "):
        raise PackageError("macOS base package README needs a title and body")
    return f"# XuanTie DebugServer {version} — macOS arm64 {identity}\n" + body


def create_release_archive(package_dir: Path, archive_path: Path) -> str:
    with tarfile.open(archive_path, mode="w:gz", format=tarfile.PAX_FORMAT) as bundle:
        bundle.add(package_dir, arcname=package_dir.name, recursive=True)
    return hash_file(archive_path)


def package(args: argparse.Namespace) -> tuple[Path, Path, str]:
    version = args.version
    package_name = f"XuanTie-DebugServer-{version}"
    output = args.output.absolute()
    if output.name != package_name:
        raise PackageError(f"--output directory must be named exactly {package_name}")
    archive_output = output.with_name(output.name + ".tar.gz")
    for path in (output, archive_output):
        if os.path.lexists(path):
            raise PackageError(f"refusing to reuse existing output: {path}")

    source = _require_directory(args.elfuse_source, "elfuse source")
    sysroot = _require_directory(args.sysroot, "guest sysroot")
    _verify_image_digest(sysroot)
    source_tree_hash = _directory_digest(source, excluded_root_names=frozenset({".git", "build"}))
    if source_tree_hash != ELFUSE_SOURCE_TREE_SHA256:
        raise PackageError(
            f"elfuse patched source inventory mismatch: got {source_tree_hash}, "
            f"expected {ELFUSE_SOURCE_TREE_SHA256}"
        )
    vendor_archive = _require_regular_file(args.vendor_archive, "vendor archive")
    helper = _require_regular_file(args.usb_helper, "cklink-usb helper", executable=True)
    library_source = _require_regular_file(args.libusb, "native libusb library")
    library_source_archive = _require_regular_file(args.libusb_source_archive, "libusb source archive")
    debugserver = _require_regular_file(REPO_ROOT / "macos" / "debugserver", "macOS debugserver", executable=True)
    readme = _require_regular_file(REPO_ROOT / "macos" / "README-r1.md", "macOS r1 base README")
    readme_contents = package_readme_contents(readme.read_text(encoding="utf-8"), package_name)
    compat_patch = _require_regular_file(REPO_ROOT / "macos" / "macos14-compat.patch", "elfuse compatibility patch")
    helper_source = _require_regular_file(REPO_ROOT / "macos" / "cklink-usb.c", "cklink-usb source")
    native_license = _require_regular_file(REPO_ROOT / "macos" / "LICENSE-MIT", "native macOS MIT license")
    elfuse_license = _require_regular_file(source / "LICENSE", "elfuse LICENSE")

    vendor_hash = hash_file(vendor_archive)
    if vendor_hash != VENDOR_SHA256:
        raise PackageError(f"vendor archive SHA-256 mismatch: got {vendor_hash}, expected {VENDOR_SHA256}")
    libusb_source_hash = hash_file(library_source_archive)
    if libusb_source_hash != LIBUSB_SOURCE_SHA256:
        raise PackageError(
            f"libusb source archive SHA-256 mismatch: got {libusb_source_hash}, "
            f"expected {LIBUSB_SOURCE_SHA256}"
        )
    source_version, source_root_name, libusb_license_text = _libusb_source_details(library_source_archive)
    if source_version != LIBUSB_SOURCE_VERSION:
        raise PackageError(
            f"libusb source archive version {source_version} does not match expected {LIBUSB_SOURCE_VERSION}"
        )
    library_version, library_version_evidence = _read_libusb_version(library_source, source_version)
    if library_version and library_version != source_version:
        raise PackageError(
            f"libusb source version {source_version} does not match library version {library_version}"
        )
    patch_hash = hash_file(compat_patch)
    if patch_hash != ELFUSE_PATCH_SHA256:
        raise PackageError(
            f"elfuse compatibility patch SHA-256 mismatch: got {patch_hash}, expected {ELFUSE_PATCH_SHA256}"
        )
    elfuse_revision = _git_revision(source)
    status_file = sysroot / "var" / "lib" / "dpkg" / "status"
    if not status_file.is_file():
        raise PackageError(f"missing Debian dpkg package status file: {status_file}")
    _parse_dpkg_status(status_file)

    output.parent.mkdir(parents=True, exist_ok=True)
    published: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix=f".{package_name}.", dir=output.parent) as temporary:
            work = Path(temporary)
            package_dir = work / package_name
            package_dir.mkdir()
            (package_dir / "bin").mkdir()
            (package_dir / "runtime" / "lib").mkdir(parents=True)
            (package_dir / "notices").mkdir()
            (package_dir / "source").mkdir()
            (package_dir / "tools").mkdir()

            _copy_file(debugserver, package_dir / "bin" / "debugserver", mode=0o755)
            os.symlink("debugserver", package_dir / "bin" / "DebugServerConsole.elf")
            _copy_file(source / "build" / "elfuse", package_dir / "runtime" / "elfuse", mode=0o755)
            _stage_usb_helper(
                helper,
                helper_source,
                package_dir / "runtime",
                package_dir / "source",
            )
            _copy_file(library_source.resolve(), package_dir / "runtime" / "lib" / "libusb-1.0.0.dylib")
            embedded_readme = package_dir / "README.md"
            embedded_readme.write_text(readme_contents, encoding="utf-8")
            embedded_readme.chmod(0o644)

            _copy_tree(
                sysroot,
                package_dir / "sysroot",
                excluded_root_names=frozenset({"opt"}),
                excluded_components=frozenset({
                    "proc", "sys", "dev", "run", "tmp", "root", "home", "mnt", "media",
                    "cache", "caches", "log", "logs", ".cache",
                }),
            )

            extracted_vendor = work / "vendor"
            safe_extract_vendor(vendor_archive, extracted_vendor)
            vendor_sysroot = package_dir / "sysroot" / "opt" / "debugserver"
            _copy_tree(extracted_vendor, vendor_sysroot)
            _ensure_guest_libusb_soname(vendor_sysroot)

            _copy_tree(
                source,
                package_dir / "source" / "elfuse",
                excluded_root_names=frozenset({".git", "build"}),
            )
            copied_source_hash = _directory_digest(package_dir / "source" / "elfuse")
            if copied_source_hash != source_tree_hash:
                raise PackageError("elfuse source inventory changed while creating the bundle")
            _copy_file(compat_patch, package_dir / "source" / "macos14-compat.patch")
            _copy_file(helper_source, package_dir / "source" / "cklink-usb.c")
            _copy_file(library_source_archive, package_dir / "source" / library_source_archive.name)
            (package_dir / "notices" / "libusb-COPYING").write_bytes(libusb_license_text)
            os.chmod(package_dir / "notices" / "libusb-COPYING", 0o644)
            _copy_file(elfuse_license, package_dir / "notices" / "elfuse-LICENSE")
            _copy_file(native_license, package_dir / "notices" / "native-MIT-LICENSE")

            (package_dir / "notices" / "provenance.json").write_text(
                json.dumps(
                    _build_provenance(
                        args=args,
                        package_dir=package_dir,
                        vendor_hash=vendor_hash,
                        library_version=library_version,
                        library_version_evidence=library_version_evidence,
                        libusb_source_version=source_version,
                        elfuse_revision=elfuse_revision,
                        patch_hash=patch_hash,
                        status_file=status_file,
                    ),
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            (package_dir / "notices" / "libusb-source.txt").write_text(
                "libusb source archive top-level directory: " + source_root_name + "\n"
                "Source URL: " + LIBUSB_SOURCE_URL.format(version=source_version) + "\n"
                "The corresponding source archive is included under source/.\n",
                encoding="utf-8",
            )
            (package_dir / "notices" / "libusb-source.txt").chmod(0o644)

            verifier_source = REPO_ROOT / "scripts" / "verify-package.py"
            _copy_file(verifier_source, package_dir / "tools" / "verify-package.py", mode=0o644)
            write_integrity_metadata(package_dir, package_name)
            _load_verifier()(package_dir)

            tar_stage = work / archive_output.name
            archive_sha256 = create_release_archive(package_dir, tar_stage)

            if any(os.path.lexists(path) for path in (output, archive_output)):
                raise PackageError("an output path appeared during packaging; refusing to overwrite it")
            os.rename(package_dir, output)
            published.append(output)
            os.rename(tar_stage, archive_output)
            published.append(archive_output)
    except Exception:
        for path in reversed(published):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif os.path.lexists(path):
                path.unlink()
        raise
    return output, archive_output, archive_sha256


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elfuse-source", required=True, type=Path, help="pinned, patched elfuse source tree")
    parser.add_argument("--sysroot", required=True, type=Path, help="cached Debian guest sysroot")
    parser.add_argument("--vendor-archive", required=True, type=Path, help="verified XuanTie Linux archive")
    parser.add_argument("--usb-helper", required=True, type=Path, help="compiled arm64 cklink-usb helper")
    parser.add_argument("--libusb", required=True, type=Path, help="relinked and ad-hoc signed arm64 libusb dylib")
    parser.add_argument("--libusb-source-archive", required=True, type=Path, help="matching libusb source tarball")
    parser.add_argument("--output", required=True, type=Path, help="new directory named XuanTie-DebugServer-<version>")
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"release suffix (default: {DEFAULT_VERSION})")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    try:
        output, archive, archive_sha256 = package(parse_args(argv))
    except (PackageError, OSError, tarfile.TarError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"package-macos: error: {exc}", file=sys.stderr)
        return 1
    print(f"Package directory: {output}")
    print(f"Release archive: {archive}")
    print(f"Archive SHA-256: {archive_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
