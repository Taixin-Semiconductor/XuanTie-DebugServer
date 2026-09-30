#!/usr/bin/env python3
"""Fresh-extraction smoke check. Never enumerate USB or attach to a target."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive.resolve()
    expected_hash, expected_name = Path(str(archive) + ".sha256").read_text().strip().split("  ", 1)
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    if expected_name != archive.name or expected_hash != archive_hash:
        raise RuntimeError("archive does not match its adjacent SHA-256 file")
    log = args.log_dir.resolve()
    log.mkdir(parents=True, exist_ok=False)
    report = {"archive": archive.name, "sha256": archive_hash, "checks": {}}

    def run(name, command, expected=0):
        result = subprocess.run(command, capture_output=True, timeout=60)
        (log / (name + ".stdout")).write_bytes(result.stdout)
        (log / (name + ".stderr")).write_bytes(result.stderr)
        (log / (name + ".exit")).write_text(str(result.returncode) + "\n")
        report["checks"][name] = {"exit": result.returncode, "expected_exit": expected}
        if result.returncode != expected:
            raise RuntimeError(f"{name} exited {result.returncode}, expected {expected}: {result.stderr.decode(errors='replace')}")
        return result

    try:
        with tempfile.TemporaryDirectory(prefix="DebugServer extracted with spaces ", dir="/private/tmp") as temporary:
            root_parent = Path(temporary)
            # This script consumes the hash-verified archive made by package-macos.py.
            run("extract", ["/usr/bin/tar", "-xzf", str(archive), "-C", str(root_parent)])
            roots = list(root_parent.iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise RuntimeError("archive does not have one package root")
            root = roots[0]
            run("manifest-before", ["python3", str(root / "tools/verify-package.py"), str(root)])
            run("doctor-offline", [str(root / "bin/debugserver"), "doctor", "--offline"])
            help_result = run("vendor-help", [str(root / "bin/debugserver"), "help"], expected=255)
            if b"-list-ice" not in help_result.stdout or b"Usage:" not in help_result.stdout:
                raise RuntimeError("guest help does not contain the expected vendor CLI")
            elfuse = str(root / "runtime/elfuse")
            dependency_result = run("guest-dependencies", [
                elfuse, "--timeout", "30", "--sysroot", str(root / "sysroot"),
                "--workdir", "/opt/debugserver", "--clear-env",
                "--env", "LD_LIBRARY_PATH=/opt/debugserver", "--env", "LD_TRACE_LOADED_OBJECTS=1",
                str(root / "sysroot/opt/debugserver/DebugServerConsole.elf")])
            if b"not found" in dependency_result.stdout + dependency_result.stderr:
                raise RuntimeError("guest loader found a missing dependency")
            for required in (b"libstdc++.so.6", b"libusb-1.0.so.0", b"libc.so.6"):
                if required not in dependency_result.stdout:
                    raise RuntimeError("guest dependency listing is incomplete")
            run("usb-helper-help", [str(root / "runtime/cklink-usb"), "--help"])
            load_commands = run("native-load-paths", ["/usr/bin/otool", "-L", str(root / "runtime/cklink-usb"),
                                                     str(root / "runtime/lib/libusb-1.0.0.dylib")])
            if b"/opt/homebrew" in load_commands.stdout or b"/usr/local/" in load_commands.stdout:
                raise RuntimeError("native runtime depends on a developer installation")
            run("manifest-after", ["python3", str(root / "tools/verify-package.py"), str(root)])
        report["result"] = "pass"
        report["usb_actions"] = "none; helper help only, doctor used --offline"
        report["hardware_retest"] = False
    except Exception as exc:
        report["result"] = "fail"
        report["error"] = str(exc)
        raise
    finally:
        (log / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
