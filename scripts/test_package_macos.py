#!/usr/bin/env python3
"""Focused tests for package extraction and release integrity metadata."""

from __future__ import annotations

import importlib.util
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load_module("package_macos", SCRIPT_DIR / "package-macos.py")
verifier = load_module("verify_package", SCRIPT_DIR / "verify-package.py")


class PackageIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.package = self.base / "XuanTie-DebugServer-V5.18.10-macos-arm64-r1"
        self.package.mkdir()
        (self.package / "bin").mkdir()
        self.exterior = self.base / "outside.txt"
        self.exterior.write_text("outside bytes", encoding="utf-8")
        executable = self.package / "bin" / "debugserver"
        executable.write_bytes(b"arm64 executable fixture\n")
        executable.chmod(0o755)
        os.symlink("../outside.txt", self.package / "outside-link")
        packager.write_integrity_metadata(self.package, self.package.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_manifest_accepts_unchanged_bundle_and_does_not_follow_external_link(self) -> None:
        self.assertGreater(verifier.verify_package(self.package), 0)
        self.exterior.write_text("changed external target", encoding="utf-8")
        self.assertGreater(verifier.verify_package(self.package), 0)

    def test_detects_regular_file_tampering(self) -> None:
        with (self.package / "bin" / "debugserver").open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(verifier.VerifyError, "hash changed"):
            verifier.verify_package(self.package)

    def test_detects_mode_and_symlink_target_changes(self) -> None:
        executable = self.package / "bin" / "debugserver"
        executable.chmod(0o700)
        with self.assertRaisesRegex(verifier.VerifyError, "mode changed"):
            verifier.verify_package(self.package)
        executable.chmod(0o755)

        link = self.package / "outside-link"
        link.unlink()
        os.symlink("../../different-target", link)
        with self.assertRaisesRegex(verifier.VerifyError, "symlink target changed"):
            verifier.verify_package(self.package)

    def test_detects_unexpected_files_and_checksum_changes(self) -> None:
        unexpected = self.package / "surprise"
        unexpected.write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(verifier.VerifyError, "unexpected package entries"):
            verifier.verify_package(self.package)
        unexpected.unlink()

        sums = self.package / "SHA256SUMS"
        sums.write_text("0" * 64 + "  bin/debugserver\n", encoding="ascii")
        with self.assertRaisesRegex(verifier.VerifyError, "SHA256SUMS mismatch"):
            verifier.verify_package(self.package)


class VendorArchiveSafetyTests(unittest.TestCase):
    def make_archive(self, archive_path: Path, *, unsafe_link: bool = False) -> None:
        with tarfile.open(archive_path, "w") as archive:
            root = tarfile.TarInfo("XUANTIE_DebugServer/")
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            archive.addfile(root)

            executable = tarfile.TarInfo("XUANTIE_DebugServer/DebugServerConsole.elf")
            executable.mode = 0o755
            executable.size = 4
            import io

            archive.addfile(executable, io.BytesIO(b"ELF!"))

            link = tarfile.TarInfo("XUANTIE_DebugServer/lib")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../../outside" if unsafe_link else "DebugServerConsole.elf"
            archive.addfile(link)

    def test_extracts_pinned_layout_and_preserves_modes_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "vendor.tar"
            destination = base / "unpacked"
            self.make_archive(archive_path)
            packager.safe_extract_vendor(archive_path, destination)
            binary = destination / "DebugServerConsole.elf"
            self.assertEqual(binary.read_bytes(), b"ELF!")
            self.assertEqual(stat.S_IMODE(binary.stat().st_mode), 0o755)
            self.assertTrue((destination / "lib").is_symlink())
            self.assertEqual(os.readlink(destination / "lib"), "DebugServerConsole.elf")

    def test_rejects_escaping_symlink_and_traversal_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "unsafe.tar"
            destination = base / "unpacked"
            self.make_archive(archive_path, unsafe_link=True)
            with self.assertRaisesRegex(packager.PackageError, "escapes extraction root"):
                packager.safe_extract_vendor(archive_path, destination)

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "traversal.tar"
            with tarfile.open(archive_path, "w") as archive:
                member = tarfile.TarInfo("XUANTIE_DebugServer/../../escape")
                member.size = 1
                import io

                archive.addfile(member, io.BytesIO(b"x"))
            with self.assertRaisesRegex(packager.PackageError, "unsafe path"):
                packager.safe_extract_vendor(archive_path, base / "unpacked")
            self.assertFalse((base.parent / "escape").exists())

    def test_rejects_special_file_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "special.tar"
            with tarfile.open(archive_path, "w") as archive:
                root = tarfile.TarInfo("XUANTIE_DebugServer/")
                root.type = tarfile.DIRTYPE
                archive.addfile(root)
                fifo = tarfile.TarInfo("XUANTIE_DebugServer/fifo")
                fifo.type = tarfile.FIFOTYPE
                archive.addfile(fifo)
            with self.assertRaisesRegex(packager.PackageError, "unsupported member type"):
                packager.safe_extract_vendor(archive_path, base / "unpacked")


class PackageCliTests(unittest.TestCase):
    def test_default_version_and_exact_output_directory_name(self) -> None:
        args = packager.parse_args([
            "--elfuse-source", "source",
            "--sysroot", "sysroot",
            "--vendor-archive", "vendor.tar.gz",
            "--usb-helper", "helper",
            "--libusb", "libusb.dylib",
            "--libusb-source-archive", "libusb.tar.bz2",
            "--output", "/tmp/not-the-release-name",
        ])
        self.assertEqual(args.version, "V5.18.10-macos-arm64-r1")
        self.assertEqual(args.libusb_source_archive, Path("libusb.tar.bz2"))
        with self.assertRaisesRegex(packager.PackageError, "must be named exactly"):
            packager.package(args)


class PackageInputTests(unittest.TestCase):
    def test_requires_the_exact_pinned_sysroot_image_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sysroot = Path(temporary)
            digest = sysroot / "image.digest"
            digest.write_text(packager.DEBIAN_IMAGE + "\n", encoding="utf-8")
            self.assertEqual(packager._verify_image_digest(sysroot), packager.DEBIAN_IMAGE)
            digest.write_text("debian:bookworm\n", encoding="utf-8")
            with self.assertRaisesRegex(packager.PackageError, "image digest mismatch"):
                packager._verify_image_digest(sysroot)

    def test_stages_compiled_helper_and_c_source_into_distinct_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            compiled = base / "cklink-usb"
            compiled.write_bytes(b"Mach-O helper fixture\x00")
            compiled.chmod(0o755)
            source = base / "cklink-usb.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            runtime_dir = base / "runtime"
            source_dir = base / "source"
            runtime_dir.mkdir()
            source_dir.mkdir()

            packager._stage_usb_helper(compiled, source, runtime_dir, source_dir)

            self.assertEqual((runtime_dir / "cklink-usb").read_bytes(), compiled.read_bytes())
            self.assertTrue((runtime_dir / "cklink-usb").stat().st_mode & 0o111)
            self.assertEqual((source_dir / "cklink-usb.c").read_bytes(), source.read_bytes())

    def test_guest_libusb_soname_is_a_relative_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vendor = Path(temporary)
            library = vendor / "libusb-1.0.so"
            library.write_bytes(b"guest ELF library")
            soname = packager._ensure_guest_libusb_soname(vendor)
            self.assertTrue(soname.is_symlink())
            self.assertEqual(os.readlink(soname), "libusb-1.0.so")
            self.assertTrue(soname.is_file())
            self.assertEqual(packager._ensure_guest_libusb_soname(vendor), soname)


if __name__ == "__main__":
    unittest.main()
