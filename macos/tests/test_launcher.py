"""Exercise launcher argument/exit/input handling with fake processes only."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

MACOS = Path(__file__).resolve().parents[1]


@unittest.skipUnless(platform.system() == "Darwin" and platform.machine() == "arm64", "native Mac launcher")
class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="debugserver paths with spaces ")
        self.root = Path(self.tmp.name).resolve()
        (self.root / "bin").mkdir()
        (self.root / "runtime").mkdir()
        self.launcher = self.root / "bin/debugserver"
        shutil.copyfile(MACOS / "debugserver", self.launcher)
        self.launcher.chmod(0o755)
        (self.root / "bin/DebugServerConsole.elf").symlink_to("debugserver")
        self.record = self.root / "calls.jsonl"
        common = f"#!{sys.executable}\nimport json, os, sys\n"
        elfuse = common + """
record = dict(tool='elfuse', args=sys.argv[1:], stdin=sys.stdin.read(),
              reset=os.getenv('ELFUSE_USBDEV_REAL_RESET'), trace=os.getenv('ELFUSE_USBDEV_TRACE'))
with open(os.environ['LAUNCHER_RECORD'], 'a') as f: f.write(json.dumps(record)+'\\n')
sys.exit(int(os.environ.get('FAKE_SERVER_EXIT', '0')))
"""
        helper = common + """
with open(os.environ['LAUNCHER_RECORD'], 'a') as f:
    f.write(json.dumps(dict(tool='usb', args=sys.argv[1:]))+'\\n')
sys.exit(int(os.environ.get('FAKE_USB_EXIT', '0')))
"""
        for name, source in (("elfuse", elfuse), ("cklink-usb", helper)):
            path = self.root / "runtime" / name
            path.write_text(source)
            path.chmod(0o755)
        self.env = dict(os.environ, LAUNCHER_RECORD=str(self.record),
                        ELFUSE_USBDEV_REAL_RESET="1", ELFUSE_USBDEV_TRACE="1")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, alias=False, **environment):
        command = self.root / "bin/DebugServerConsole.elf" if alias else self.launcher
        return subprocess.run([str(command), *args], env=dict(self.env, **environment),
                              capture_output=True, text=True)

    def records(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()] if self.record.exists() else []

    def test_list_sets_watchdog_and_never_activates(self):
        result = self.call("list", FAKE_SERVER_EXIT="23")
        self.assertEqual(result.returncode, 23, result.stderr)
        calls = self.records()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "elfuse")
        self.assertEqual(calls[0]["args"][-1], "-list-ice")
        self.assertEqual(calls[0]["args"][:2], ["--timeout", "30"])
        self.assertEqual(calls[0]["stdin"], "no\n")
        self.assertEqual(calls[0]["reset"], "0")
        self.assertEqual(calls[0]["trace"], "0")

    def test_run_preserves_spaced_arguments_without_timeout(self):
        result = self.call("run", "--debug", "connect events")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.records()[0]["args"]
        self.assertEqual(args[-2:], ["--debug", "connect events"])
        self.assertNotIn("--timeout", args)
        self.assertIn(str(self.root / "sysroot"), args)

    def test_console_alias_preserves_vendor_help_and_exit(self):
        result = self.call("--help", alias=True, FAKE_SERVER_EXIT="255")
        self.assertEqual(result.returncode, 255, result.stderr)
        args = self.records()[0]["args"]
        self.assertEqual(args[-1], "--help")
        self.assertNotIn("--timeout", args)

    def test_activation_is_explicit_and_not_a_guest_call(self):
        result = self.call("activate", "--serial", "TEST_SERIAL")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [{"tool": "usb", "args": ["--activate", "--serial", "TEST_SERIAL"]}])

    def test_failed_target_selection_never_launches_server(self):
        result = self.call("check", FAKE_USB_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records(), [{"tool": "usb", "args": ["--require-single-normal"]}])

    def test_check_guards_selection_and_uses_tested_flags(self):
        result = self.call("check", "--serial", "TEST_SERIAL")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.records()
        self.assertEqual(calls[0], {"tool": "usb", "args": ["--require-single-normal", "--serial", "TEST_SERIAL"]})
        self.assertEqual(calls[1]["args"][-10:], ["-arch", "csky", "-setcdi", "2", "-setclk", "2500k",
                                                  "-check-target", "-skip-enter", "--debug", "connect"])

    def test_usage_and_bad_arguments_do_not_launch_tools(self):
        self.assertEqual(self.call("--help").returncode, 0)
        self.assertEqual(self.call("list", "--activate").returncode, 2)
        self.assertEqual(self.records(), [])


if __name__ == "__main__":
    unittest.main()
