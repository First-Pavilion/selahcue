#!/usr/bin/env python3
"""Fail-closed input inventory for the unvalidated Ubuntu x86_64/.deb candidate.

This inspects source/configuration and staged native inputs. It never installs
packages, creates placeholders, reads credentials or starts a build. Passing
means input/header checks only, not a runnable, ABI-compatible or signed release.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

TARGET = "x86_64-unknown-linux-gnu"
OPERATOR = Path("implementation/desktop/crates/selahcue-operator")
PKG_CONFIG = ("webkit2gtk-4.1", "gtk+-3.0", "ayatana-appindicator3-0.1",
              "librsvg-2.0", "x11", "xkbcommon", "alsa")
TOOLS = ("cargo", "rustc", "pkg-config", "cc", "cmake", "clang", "perl", "dpkg-deb")
APT_BUILD_PACKAGES = ("build-essential", "pkg-config", "libwebkit2gtk-4.1-dev",
                      "libgtk-3-dev", "libayatana-appindicator3-dev", "librsvg2-dev",
                      "libx11-dev", "libxkbcommon-dev", "libasound2-dev", "cmake",
                      "libclang-dev", "perl", "patchelf")


def elf_problem(path: Path, executable: bool = False) -> str | None:
    try:
        if not path.is_file():
            return "missing regular file"
        with path.open("rb") as stream:
            header = stream.read(64)
        if len(header) < 64 or header[:7] != b"\x7fELF\x02\x01\x01":
            return "not a complete ELF64 little-endian header (empty compile placeholders are forbidden)"
        if struct.unpack_from("<H", header, 18)[0] != 62:
            return "ELF architecture is not x86_64"
        if executable and not os.access(path, os.X_OK):
            return "sidecar has no executable permission"
    except OSError as error:
        return f"cannot read native input: {error.strerror}"
    return None


def inspect_repo(root: Path, target: str = TARGET, ndi: str = "undecided") -> dict:
    root = root.resolve()
    report = {"candidate": {"os": "Ubuntu 24.04", "target": target, "format": "deb"},
              "matrix_status": "candidate-not-validated", "release_ready": False,
              "input_checks_passed": False, "checks": [],
              "apt_build_packages": list(APT_BUILD_PACKAGES),
              "not_verified": ["native compilation", "ELF dependency/rpath closure", "clean install/uninstall",
                               "X11/Wayland/display/GPU/audio/keyring behavior", "pilot profile/expiry/scanning",
                               "NDI redistribution and packaging layout approval"]}

    def check(key, okay, detail):
        report["checks"].append({"id": key, "status": "pass" if okay else "blocked", "detail": detail})

    check("candidate-target", target == TARGET,
          f"Only {TARGET} is inventoried; other CPU/ABI combinations need separate evidence")
    path = root / OPERATOR / "tauri.conf.json"
    try:
        cfg = json.loads(path.read_text())
        if not isinstance(cfg, dict) or not isinstance(cfg.get("bundle"), dict):
            raise ValueError("expected configuration object with a bundle object")
    except (OSError, ValueError) as error:
        check("configuration", False, f"Cannot inspect {OPERATOR}/tauri.conf.json: {error}")
        return report
    check("configuration", True, str(OPERATOR / "tauri.conf.json"))
    bundle = cfg["bundle"]
    targets = bundle.get("targets", [])
    check("package-format", isinstance(targets, list) and "deb" in targets and "nsis" not in targets,
          f"Configured targets: {targets}; a reviewed effective Linux config must select deb, not the current Windows NSIS target")
    resources = bundle.get("resources", {})
    names = list(resources) + list(resources.values()) if isinstance(resources, dict) else resources
    windows = [name for name in names if isinstance(name, str) and name.lower().endswith((".dll", ".exe"))] if isinstance(names, list) else ["invalid resources shape"]
    check("windows-resources", not windows,
          f"Windows resource entries must not enter the Linux package: {windows}")
    build = cfg.get("build", {})
    frontend = build.get("frontendDist") if isinstance(build, dict) else None
    check("frontend", isinstance(frontend, str) and (root / OPERATOR / frontend / "index.html").is_file(),
          "Tracked operator frontend must have a local index.html; no network URL or empty directory")
    bins = bundle.get("externalBin", [])
    declared = isinstance(bins, list) and "binaries/selahcue-output" in bins
    check("sidecar-declaration", declared, "externalBin must declare binaries/selahcue-output")
    if declared:
        path = root / OPERATOR / f"binaries/selahcue-output-{target}"
        problem = elf_problem(path, executable=True)
        check("sidecar", problem is None, f"{path.relative_to(root)}: {problem or 'ELF64 x86_64 header/executable mode present; link/runtime not proven'}")
    check("ndi-decision", ndi in ("enabled", "disabled"),
          f"NDI choice is {ndi}; build profile must record enabled or disabled rather than silently losing a feature")
    if ndi == "enabled":
        sdk = root / "implementation/desktop/vendor/ndi/linux"
        header = sdk / "include/Processing.NDI.Lib.h"
        library = sdk / "lib/x86_64-linux-gnu/libndi.so"
        problem = elf_problem(library)
        okay = header.is_file() and header.stat().st_size > 0 and problem is None
        check("ndi-sdk", okay,
              "Need nonempty Linux SDK header and x86_64 libndi.so in vendor/ndi/linux; "
              f"runtime input: {problem or 'header checked only; redistribution and $ORIGIN/DT_NEEDED closure still require evidence'}")
    report["input_checks_passed"] = all(c["status"] == "pass" for c in report["checks"])
    return report


def inspect_host() -> dict:
    result = {"system": platform.system(), "machine": platform.machine(), "checks": []}
    release = Path("/etc/os-release")
    result["os_release"] = dict(line.split("=", 1) for line in release.read_text().splitlines()
                                if "=" in line) if release.is_file() else {}
    candidate = (result["system"] == "Linux" and result["machine"] == "x86_64"
                 and result["os_release"].get("ID", "").strip('"') == "ubuntu"
                 and result["os_release"].get("VERSION_ID", "").strip('"') == "24.04")
    result["checks"].append({"id": "candidate-host", "status": "pass" if candidate else "blocked"})
    for name in TOOLS:
        result["checks"].append({"id": f"tool:{name}", "status": "pass" if shutil.which(name) else "blocked"})
    if shutil.which("pkg-config"):
        for name in PKG_CONFIG:
            child = subprocess.run(["pkg-config", "--modversion", name], capture_output=True,
                                   text=True, timeout=10, check=False)
            result["checks"].append({"id": f"native:{name}", "status": "pass" if child.returncode == 0 else "blocked",
                                     "version": child.stdout.strip() if child.returncode == 0 else None})
    else:
        result["checks"].append({"id": "native-pkg-config", "status": "blocked"})
    result["input_checks_passed"] = all(c["status"] == "pass" for c in result["checks"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target", default=TARGET)
    parser.add_argument("--ndi", choices=("enabled", "disabled", "undecided"), default="undecided")
    parser.add_argument("--check-host", action="store_true")
    args = parser.parse_args()
    report = inspect_repo(args.root, args.target, args.ndi)
    if args.check_host:
        report["host"] = inspect_host()
        report["input_checks_passed"] &= report["host"]["input_checks_passed"]
    print(json.dumps(report, indent=2))
    return 0 if report["input_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
