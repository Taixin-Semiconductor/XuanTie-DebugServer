#!/usr/bin/env python3
"""Check a packaged release manifest and its SHA256SUMS without following links."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "manifest.json"
SUMS_NAME = "SHA256SUMS"


class VerifyError(Exception):
    """The bundle does not match its integrity metadata."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_manifest_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\n" in value or "\r" in value:
        raise VerifyError(f"invalid manifest path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise VerifyError(f"unsafe manifest path: {value!r}")
    if path.as_posix() != value:
        raise VerifyError(f"non-canonical manifest path: {value!r}")
    return value


def _actual_entries(root: Path) -> dict[str, tuple[str, int, Path]]:
    entries: dict[str, tuple[str, int, Path]] = {}

    def walk(directory: Path, relative: PurePosixPath) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            rel = relative / entry.name
            name = rel.as_posix()
            if "\n" in name or "\r" in name or "\\" in name:
                raise VerifyError(f"package path cannot be represented safely: {name!r}")
            path = Path(entry.path)
            info = entry.stat(follow_symlinks=False)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISDIR(info.st_mode):
                entries[name] = ("directory", mode, path)
                walk(path, rel)
            elif stat.S_ISREG(info.st_mode):
                entries[name] = ("file", mode, path)
            elif stat.S_ISLNK(info.st_mode):
                entries[name] = ("symlink", mode, path)
            else:
                raise VerifyError(f"unsupported special file in package: {name}")

    walk(root, PurePosixPath())
    return entries


def _read_checksum_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise VerifyError(f"cannot read {SUMS_NAME}: {exc}") from exc
    checksums: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise VerifyError(f"invalid checksum line: {line!r}")
        digest, name = match.groups()
        _valid_manifest_path(name)
        if name in checksums:
            raise VerifyError(f"duplicate checksum entry: {name}")
        checksums[name] = digest
    return checksums


def verify_package(package_dir: Path | str) -> int:
    root = Path(package_dir)
    if root.is_symlink() or not root.is_dir():
        raise VerifyError(f"package path must be a directory: {root}")
    manifest_path = root / MANIFEST_NAME
    sums_path = root / SUMS_NAME
    for path, label in ((manifest_path, MANIFEST_NAME), (sums_path, SUMS_NAME)):
        if path.is_symlink() or not path.is_file():
            raise VerifyError(f"missing or invalid {label}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {MANIFEST_NAME}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise VerifyError("unsupported manifest schema")
    if manifest.get("package") != root.name:
        raise VerifyError(f"manifest package name does not match directory {root.name!r}")
    records = manifest.get("entries")
    if not isinstance(records, list):
        raise VerifyError("manifest entries must be a list")

    expected: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise VerifyError("manifest entry must be an object")
        name = _valid_manifest_path(record.get("path"))
        if name in (MANIFEST_NAME, SUMS_NAME):
            raise VerifyError(f"manifest must not self-reference metadata: {name}")
        if name in expected:
            raise VerifyError(f"duplicate manifest entry: {name}")
        entry_type = record.get("type")
        if entry_type not in ("directory", "file", "symlink"):
            raise VerifyError(f"invalid type for {name}: {entry_type!r}")
        mode = record.get("mode")
        if not isinstance(mode, int) or isinstance(mode, bool) or mode < 0 or mode > 0o7777:
            raise VerifyError(f"invalid mode for {name}")
        if entry_type in ("file", "symlink"):
            if not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
                raise VerifyError(f"invalid SHA-256 for {name}")
        if entry_type == "symlink" and not isinstance(record.get("target"), str):
            raise VerifyError(f"missing symlink target for {name}")
        expected[name] = record

    actual = _actual_entries(root)
    actual_package_entries = set(actual) - {MANIFEST_NAME, SUMS_NAME}
    expected_paths = set(expected)
    missing = sorted(expected_paths - actual_package_entries)
    unexpected = sorted(actual_package_entries - expected_paths)
    if missing:
        raise VerifyError(f"missing package entries: {', '.join(missing[:8])}")
    if unexpected:
        raise VerifyError(f"unexpected package entries: {', '.join(unexpected[:8])}")

    regular_file_hashes: dict[str, str] = {}
    for name, record in expected.items():
        actual_type, actual_mode, path = actual[name]
        if actual_type != record["type"]:
            raise VerifyError(f"entry type changed for {name}: {actual_type} != {record['type']}")
        if actual_mode != record["mode"]:
            raise VerifyError(f"mode changed for {name}: {actual_mode:o} != {record['mode']:o}")
        if actual_type == "file":
            digest = _hash_file(path)
            if digest != record["sha256"]:
                raise VerifyError(f"file hash changed for {name}")
            regular_file_hashes[name] = digest
        elif actual_type == "symlink":
            target = os.readlink(path)
            if target != record["target"]:
                raise VerifyError(f"symlink target changed for {name}")
            digest = hashlib.sha256(os.fsencode(target)).hexdigest()
            if digest != record["sha256"]:
                raise VerifyError(f"symlink target hash changed for {name}")

    checksums = _read_checksum_file(sums_path)
    if checksums != regular_file_hashes:
        missing_sums = sorted(set(regular_file_hashes) - set(checksums))
        extra_sums = sorted(set(checksums) - set(regular_file_hashes))
        if missing_sums:
            raise VerifyError(f"missing SHA256SUMS entries: {', '.join(missing_sums[:8])}")
        if extra_sums:
            raise VerifyError(f"unexpected SHA256SUMS entries: {', '.join(extra_sums[:8])}")
        changed = sorted(name for name in checksums if checksums[name] != regular_file_hashes.get(name))
        raise VerifyError(f"SHA256SUMS mismatch: {', '.join(changed[:8])}")
    return len(expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path, help="release package directory")
    args = parser.parse_args(argv)
    try:
        count = verify_package(args.package_dir)
    except (VerifyError, OSError) as exc:
        print(f"verify-package: error: {exc}", file=sys.stderr)
        return 1
    print(f"Verified {count} entries in {args.package_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
