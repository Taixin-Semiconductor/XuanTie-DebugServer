#!/usr/bin/env python3
"""Tests for preparing the canonical DebugServer macOS arm64 r2 archive."""

from contextlib import redirect_stdout
import hashlib
import io
import runpy
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
PREPARER = runpy.run_path(str(REPO / "scripts" / "prepare-debugserver-r2.py"))
PREPARER_GLOBALS = PREPARER["main"].__globals__


class PrepareDebugServerR2Tests(unittest.TestCase):
    def make_r1_archive(self, base: Path) -> tuple[Path, dict[str, bytes]]:
        root = base / "tree" / PREPARER["R1_PACKAGE"]
        files = {
            "README.md": b"# XuanTie DebugServer V5.18.10 - macOS arm64 r1\n",
            "bin/debugserver": (
                b"#!/bin/sh\n"
                b"case \"$1\" in\n"
                b"  doctor) echo 'offline doctor passed'; exit 0 ;;\n"
                b"  help) echo 'XuanTie Debugger Server Usage'; exit 255 ;;\n"
                b"  *) exit 2 ;;\n"
                b"esac\n"
            ),
            "bin/cklink-usb": b"native usb helper fixture\n",
            "runtime/elfuse": b"elfuse runtime fixture\n",
            "runtime/lib/libusb-1.0.0.dylib": b"libusb fixture\n",
            "sysroot/etc/hosts": b"127.0.0.1 localhost\n",
            "sysroot/opt/debugserver/DebugServerConsole.elf": b"vendor payload fixture\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o755 if relative in ("bin/debugserver", "bin/cklink-usb", "runtime/elfuse",
                                             "sysroot/opt/debugserver/DebugServerConsole.elf") else 0o644)
        (root / "bin/DebugServerConsole.elf").symlink_to("debugserver")
        archive = base / PREPARER["R1_NAME"]
        PREPARER["create_archive"](root, archive)
        return archive, files

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_main_builds_canonical_archive_without_external_sidecar(self) -> None:
        with tempfile.TemporaryDirectory(prefix="debugserver-r2-test-") as temporary:
            base = Path(temporary)
            source, expected_files = self.make_r1_archive(base)
            previous_pin = PREPARER_GLOBALS["R1_SHA256"]
            PREPARER_GLOBALS["R1_SHA256"] = self.digest(source)
            self.addCleanup(lambda: PREPARER_GLOBALS.__setitem__("R1_SHA256", previous_pin))
            output = base / (PREPARER["R2_PACKAGE"] + ".tar.gz")

            stdout = io.StringIO()
            with patch("sys.argv", ["prepare-debugserver-r2.py", "--r1-archive", str(source),
                                     "--output", str(output)]), redirect_stdout(stdout):
                self.assertEqual(PREPARER["main"](), 0)

            self.assertTrue(output.is_file())
            self.assertFalse(output.with_suffix(output.suffix + ".sha256").exists())
            self.assertIn("archive_sha256: " + self.digest(output), stdout.getvalue())
            self.assertIn("package_identity: " + PREPARER["R2_PACKAGE"], stdout.getvalue())
            self.assertIn("offline_doctor: passed", stdout.getvalue())
            self.assertIn("vendor_help: passed (exit 255)", stdout.getvalue())

            extracted = base / "fresh"
            bundle = PREPARER["safe_extract"](output, extracted, PREPARER["R2_PACKAGE"])
            PREPARER["verify_integrity"](bundle)
            hosts = (bundle / "sysroot/etc/hosts").read_text(encoding="utf-8")
            self.assertEqual(sum(line.split("#", 1)[0].split() == ["127.0.0.1", "elfuse"]
                                 for line in hosts.splitlines()), 1)

            source_root = PREPARER["safe_extract"](source, base / "source-extracted", PREPARER["R1_PACKAGE"])
            for relative in expected_files:
                if relative in ("README.md", "sysroot/etc/hosts"):
                    continue
                self.assertEqual((bundle / relative).read_bytes(), (source_root / relative).read_bytes(), relative)
            self.assertEqual((bundle / "bin/DebugServerConsole.elf").readlink(), Path("debugserver"))

            readme = (bundle / "README.md").read_text(encoding="utf-8")
            self.assertIn("macOS arm64 r2", readme.splitlines()[0])
            self.assertIn("source prototype", readme)
            self.assertIn("does not validate this archived r2 bundle against", readme)
            for obsolete in ("r2-local", "unpublished", "Local r2 hostname"):
                self.assertNotIn(obsolete.lower(), readme.lower())
            notes = (bundle / "RELEASE-NOTES.md").read_text(encoding="utf-8")
            self.assertIn("127.0.0.1 elfuse", notes)
            self.assertNotIn("local", notes.lower())

    def test_prepare_tree_adds_exact_loopback_mapping_even_if_other_alias_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="debugserver-r2-hosts-") as temporary:
            base = Path(temporary)
            archive, _ = self.make_r1_archive(base)
            root = PREPARER["safe_extract"](archive, base / "unpacked", PREPARER["R1_PACKAGE"])
            (root / "sysroot/etc/hosts").write_text("127.0.1.1 elfuse\n", encoding="utf-8")

            PREPARER["prepare_tree"](root, archive.name)

            hosts = (root.parent / PREPARER["R2_PACKAGE"] / "sysroot/etc/hosts").read_text(encoding="utf-8")
            self.assertEqual(hosts, "127.0.1.1 elfuse\n127.0.0.1 elfuse\n")

    def test_main_rejects_wrong_r1_checksum_before_writing_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="debugserver-r2-pin-") as temporary:
            base = Path(temporary)
            source, _ = self.make_r1_archive(base)
            previous_pin = PREPARER_GLOBALS["R1_SHA256"]
            PREPARER_GLOBALS["R1_SHA256"] = "0" * 64
            self.addCleanup(lambda: PREPARER_GLOBALS.__setitem__("R1_SHA256", previous_pin))
            output = base / (PREPARER["R2_PACKAGE"] + ".tar.gz")
            with patch("sys.argv", ["prepare-debugserver-r2.py", "--r1-archive", str(source),
                                     "--output", str(output)]):
                with self.assertRaises(PREPARER["PackageError"]):
                    PREPARER["main"]()
            self.assertFalse(output.exists())

    def test_safe_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="debugserver-r2-traversal-") as temporary:
            base = Path(temporary)
            archive_path = base / "malicious.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                entry = tarfile.TarInfo("../outside")
                entry.size = 3
                archive.addfile(entry, io.BytesIO(b"bad"))
            with self.assertRaises(PREPARER["PackageError"]):
                PREPARER["safe_extract"](archive_path, base / "unpacked", PREPARER["R2_PACKAGE"])
            self.assertFalse((base / "outside").exists())


if __name__ == "__main__":
    unittest.main()
