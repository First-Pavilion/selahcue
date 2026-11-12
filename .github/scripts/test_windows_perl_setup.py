#!/usr/bin/env python3
"""Execute the rust job's real Perl setup block in PowerShell with isolated PATHs.

Usage: python3 .github/scripts/test_windows_perl_setup.py --pwsh /absolute/path/to/pwsh

POSIX executable fixtures control probe exits and record arguments. This proves
PowerShell selection/export behavior, not native Windows Perl/module availability.
No PowerShell mocking, package installation, shared PATH change or Rust build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml


PROBE_ARGS = [
    "-MIPC::Cmd", "-MParams::Check", "-MLocale::Maketext::Simple", "-e",
    'die "expected native Windows Perl\\n" unless $^O eq "MSWin32"; print "$^X ($^O) Perl $]\\n";',
]
SENTINEL = "UNRELATED_BINDING=preserved\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pwsh", required=True, type=Path)
    parser.add_argument("--workflow", type=Path, default=Path(".github/workflows/ci.yml"))
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("these executable fixtures require POSIX; use hosted CI for native Windows proof")
    pwsh = args.pwsh.resolve(strict=True)
    workflow = yaml.safe_load(args.workflow.read_text())
    blocks = [step["run"] for step in workflow["jobs"]["rust"]["steps"]
              if step.get("name") == "Verify Perl is on PATH for the vendored-OpenSSL build (Windows only)"]
    if len(blocks) != 1:
        raise RuntimeError("expected exactly one rust-job Perl setup block")
    block = blocks[0]
    print(f"workflow={args.workflow} block_sha256={hashlib.sha256(block.encode()).hexdigest()}", flush=True)
    failures = []
    cases = [
        ("multiple candidates", [("first", 0), ("second", 0)], True),
        ("one candidate", [("only", 0)], True),
        ("path containing spaces", [("Program Files/Perl bin", 0)], True),
        ("no match", [], False),
        ("probe failure", [("first", 23), ("second", 0)], False),
    ]
    with tempfile.TemporaryDirectory(prefix="windows-perl-setup-") as directory:
        root = Path(directory)
        script = root / "actual-workflow-block.ps1"
        # Match the Actions pwsh wrapper's terminating-error behavior. The run
        # text itself is extracted unchanged, including probe and environment export.
        script.write_text("$ErrorActionPreference = 'Stop'\n" + block)
        recorder = root / "record_probe.py"
        recorder.write_text(
            "import json, os, sys\n"
            "with open(os.environ['PERL_FIXTURE_LOG'], 'a') as log:\n"
            "    log.write(json.dumps({'candidate': sys.argv[1], 'args': sys.argv[3:]}) + '\\n')\n"
            "sys.exit(int(sys.argv[2]))\n"
        )
        for index, (label, candidates, success) in enumerate(cases):
            case = root / str(index)
            case.mkdir()
            executable_paths = []
            for name, exit_code in candidates:
                executable = case / name / "perl"
                executable.parent.mkdir(parents=True)
                executable.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(arg) for arg in
                                      [sys.executable, str(recorder), name, str(exit_code)]) + ' "$@"\n')
                executable.chmod(0o700)
                executable_paths.append(executable)
            empty_path = case / "empty"
            empty_path.mkdir()
            binding = case / "github-env"
            binding.write_text(SENTINEL)
            log = case / "probe.jsonl"
            env = {**os.environ, "PATH": os.pathsep.join(str(p.parent) for p in executable_paths) or str(empty_path),
                   "GITHUB_ENV": str(binding), "PERL_FIXTURE_LOG": str(log),
                   "POWERSHELL_TELEMETRY_OPTOUT": "1", "POWERSHELL_UPDATECHECK": "Off",
                   "XDG_CACHE_HOME": str(case / "cache"),
                   "XDG_CONFIG_HOME": str(case / "config"), "DOTNET_CLI_HOME": str(case)}
            env.pop("OPENSSL_SRC_PERL", None)
            command = [str(pwsh), "-NoLogo", "-NoProfile", "-NonInteractive"]
            enumeration = subprocess.run(command + ["-Command",
                "@(Get-Command perl -CommandType Application -ErrorAction SilentlyContinue) | "
                "ForEach-Object { \"$($_.GetType().FullName)|$($_.Source)\" }; exit 0"],
                env=env, text=True, capture_output=True, timeout=15)
            expected_enumeration = [f"System.Management.Automation.ApplicationInfo|{p}" for p in executable_paths]
            if enumeration.returncode or enumeration.stdout.splitlines() != expected_enumeration:
                failures.append(f"{label}: unexpected real Get-Command enumeration: {enumeration.stdout!r} {enumeration.stderr!r}")
            print(f"{label}: Get-Command returned {len(enumeration.stdout.splitlines())} ApplicationInfo candidate(s) in PATH order", flush=True)
            result = subprocess.run(command + ["-File", str(script)], env=env, text=True,
                                    capture_output=True, timeout=15)
            actual_binding = binding.read_text(encoding="utf-8-sig")
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            expected_binding = SENTINEL + (f"OPENSSL_SRC_PERL={executable_paths[0]}\n" if success else "")
            expected_calls = ([{"candidate": candidates[0][0], "args": PROBE_ARGS}] if candidates else [])
            errors = []
            if (result.returncode == 0) != success:
                errors.append(f"expected success={success}; exit={result.returncode}")
            if actual_binding != expected_binding:
                errors.append(f"unexpected GITHUB_ENV: {actual_binding!r}; expected {expected_binding!r}")
            if calls != expected_calls:
                errors.append(f"unexpected probe calls: {calls!r}; expected {expected_calls!r}")
            if errors:
                failures.append(f"{label}: {'; '.join(errors)}\nstdout={result.stdout}\nstderr={result.stderr}")
            else:
                print(f"PASS {label}: exit={result.returncode}, probes={len(calls)}, binding={'one scalar' if success else 'unchanged'}", flush=True)
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print(f"{len(cases)} cases, {len(failures)} failures")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
