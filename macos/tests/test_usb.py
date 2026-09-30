"""Test activation guards with a mock libusb; never touch physical USB."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

MACOS = Path(__file__).resolve().parents[1]


class USBGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cklink-unit-")
        cls.binary = Path(cls.tmp.name) / "cklink-usb"
        include = os.environ.get("LIBUSB_INCLUDE", "/opt/homebrew/opt/libusb/include/libusb-1.0")
        subprocess.run(["clang", "-Wall", "-Wextra", "-Werror", "-I" + include,
                        str(MACOS / "cklink-usb.c"), str(MACOS / "tests/fake-usb.c"),
                        "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, scenario, *args):
        env = dict(os.environ, USB_TEST_SCENARIO=scenario)
        return subprocess.run([str(self.binary), *args], env=env, capture_output=True, text=True)

    def test_inspection_never_sets_configuration(self):
        for scenario in ("loader", "configured", "normal", "two-loaders", "absent"):
            with self.subTest(scenario=scenario):
                result = self.call(scenario, "--inspect")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("STATE_CHANGE", result.stdout)

    def test_single_unconfigured_loader_sets_once(self):
        result = self.call("loader", "--activate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("STATE_CHANGE"), 1)
        self.assertIn("STATE_CHANGE serial=FIRST value=1", result.stdout)

    def test_ambiguous_loader_requires_serial(self):
        result = self.call("two-loaders", "--activate")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("STATE_CHANGE", result.stdout)
        selected = self.call("two-loaders", "--activate", "--serial", "SECOND")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(selected.stdout.count("STATE_CHANGE"), 1)
        self.assertIn("STATE_CHANGE serial=SECOND value=1", selected.stdout)

    def test_wrong_serial_refuses(self):
        result = self.call("loader", "--activate", "--serial", "MISSING")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("STATE_CHANGE", result.stdout)

    def test_guard_failures_never_set_configuration(self):
        for scenario in ("configured", "normal", "absent", "denied", "config-error", "no-config-one"):
            with self.subTest(scenario=scenario):
                result = self.call(scenario, "--activate")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("STATE_CHANGE", result.stdout)

    def test_unreadable_serial_cannot_match_requested_identity(self):
        result = self.call("serial-error", "--activate", "--serial", "FIRST")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("STATE_CHANGE", result.stdout)

    def test_failed_request_is_not_retried(self):
        result = self.call("set-error", "--activate")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count("STATE_CHANGE"), 1)

    def test_target_check_requires_only_one_normal_probe(self):
        passed = self.call("normal", "--require-single-normal", "--serial", "FIRST")
        self.assertEqual(passed.returncode, 0, passed.stderr)
        for scenario in ("loader", "two-normal", "normal-two-mixed", "absent"):
            with self.subTest(scenario=scenario):
                result = self.call(scenario, "--require-single-normal", "--serial", "FIRST")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("STATE_CHANGE", result.stdout)

    def test_invalid_arguments_fail_before_enumeration(self):
        for args in (("--activate", "--serial", ""), ("--reset",), ("--inspect", "--serial", "FIRST")):
            with self.subTest(args=args):
                result = self.call("loader", *args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("STATE_CHANGE", result.stdout)


if __name__ == "__main__":
    unittest.main()
