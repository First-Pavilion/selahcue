#!/usr/bin/env python3
"""Stage the default-feature operator test and verify the joint API test results."""

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OPERATOR = "selahcue-operator"
RUST_TEST = "account::tests::controller::django_g1_real_api"
BINARY = "operator-test"
MANIFEST = "manifest.json"
MAX_ARTIFACT = 256 * 1024 * 1024
MAX_REPORT = 32 * 1024 * 1024
JOINT_MODULE = "tests/test_native_account_controller_integration.py"
JOINT_CLASS = "tests.test_native_account_controller_integration"
JOINT_TEST = "test_native_account_controller_against_local_platform_api"


class GateError(Exception):
    pass


def plain_path(path):
    """Resolve only existing canonical paths with no symlink or parent aliases."""
    path = path.absolute()
    if path.resolve(strict=True) != path:
        raise GateError(f"symlink or ambiguous path: {path}")
    return path


def file_path(path):
    path = plain_path(path)
    if not path.is_file():
        raise GateError(f"not a regular file: {path}")
    return path


def read_limited(path, limit):
    with file_path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise GateError(f"{path.name} exceeds {limit} bytes")
    return data


def checked_source(source):
    if not re.fullmatch(r"[a-f0-9]{40}", source):
        raise GateError("expected a full checkout source SHA")
    return source


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_size(binary, manifest_size=0):
    size = binary.stat().st_size
    if not 0 < size or size + manifest_size > MAX_ARTIFACT:
        raise GateError(
            f"{binary.name} is {size} bytes with a {manifest_size}-byte manifest; "
            f"expected a nonempty binary and a bundle no larger than {MAX_ARTIFACT} bytes"
        )
    return size


def run_command(args, *, timeout=30):
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout


def stage(cargo_json, source_sha, output_dir):
    source_sha = checked_source(source_sha)
    candidates = []
    for line in read_limited(cargo_json, MAX_REPORT).splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("reason") != "compiler-artifact":
            continue
        target = record.get("target")
        profile = record.get("profile")
        features = record.get("features")
        if not isinstance(target, dict) or not isinstance(profile, dict) or not isinstance(features, list):
            raise GateError("malformed Cargo compiler-artifact record")
        if (
            target.get("name") == OPERATOR
            and target.get("kind") == ["bin"]
            and profile.get("test") is True
            and "default" in features and "native-account" in features
            and isinstance(record.get("executable"), str)
            and record["executable"]
        ):
            candidates.append(Path(record["executable"]))
    if len(candidates) != 1:
        raise GateError(f"expected exactly one default-feature operator test executable, found {len(candidates)}")
    if not candidates[0].is_absolute():
        raise GateError("Cargo executable path must be absolute")
    executable = file_path(candidates[0])
    # A new directory and fixed filenames keep staging separate from Cargo's files.
    output_dir = plain_path(output_dir.parent) / output_dir.name
    output_dir.mkdir(exist_ok=False)
    binary = output_dir / BINARY
    shutil.copyfile(executable, binary)
    run_command(["strip", "--strip-debug", "--", str(binary)], timeout=60)
    check_size(binary)
    manifest = {
        "source_sha": source_sha,
        "sha256": sha256(binary),
        "test_name": RUST_TEST,
        "default_features": True,
    }
    receipt = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    size = check_size(binary, len(receipt))
    (output_dir / MANIFEST).write_bytes(receipt)
    print(f"Stripped operator test size: {size} bytes ({size + len(receipt)} bytes with manifest)")


def verify(artifact_dir, expected_source_sha):
    expected_source_sha = checked_source(expected_source_sha)
    directory = plain_path(artifact_dir)
    if {path.name for path in directory.iterdir()} != {BINARY, MANIFEST}:
        raise GateError("artifact must contain exactly operator-test and manifest.json")
    receipt = read_limited(directory / MANIFEST, 4096)
    manifest = json.loads(receipt)
    if not isinstance(manifest, dict) or set(manifest) != {"source_sha", "sha256", "test_name", "default_features"}:
        raise GateError("unexpected operator test manifest fields")
    if manifest["source_sha"] != expected_source_sha:
        raise GateError("operator artifact source SHA does not match the checkout")
    if manifest["test_name"] != RUST_TEST or manifest["default_features"] is not True:
        raise GateError("manifest must describe the exact default-feature operator test")
    binary = file_path(directory / BINARY)
    check_size(binary, len(receipt))
    if manifest["sha256"] != sha256(binary):
        raise GateError("operator artifact SHA-256 does not match the manifest")

    # Artifact downloads do not preserve permissions. Restore execution only
    # once we have verified the source and the contents of the downloaded file.
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    libraries = run_command(["ldd", str(binary)])
    print(libraries.rstrip())
    if not libraries.strip() or "not found" in libraries:
        raise GateError("operator test has missing shared libraries")
    tests = run_command([str(binary), "--list", "--ignored"])
    if tests.splitlines().count(f"{RUST_TEST}: test") != 1:
        raise GateError("operator binary does not list the exact ignored test")
    return binary


def verify_results(junit, nodeids, evidence=None):
    prefix = f"{JOINT_MODULE}::"
    expected = {}
    for line in read_limited(nodeids, 1024 * 1024).decode("utf-8").splitlines():
        if not line.startswith(prefix):
            continue  # pytest --collect-only -q also prints a summary
        name = line.removeprefix(prefix)
        if not re.fullmatch(re.escape(JOINT_TEST) + r"\[[^\[\]]+\]", name) or name in expected:
            raise GateError("invalid or duplicate collected joint node ID")
        expected[name] = []
    if not expected:
        raise GateError("no joint tests were collected")

    root = ET.fromstring(read_limited(junit, MAX_REPORT))
    if root.tag not in {"testsuite", "testsuites"}:
        raise GateError("expected pytest JUnit XML")
    unexpected = 0
    for case in root.iter("testcase"):
        name = case.get("name", "")
        if case.get("classname") != JOINT_CLASS or not name.startswith(f"{JOINT_TEST}["):
            continue
        if name not in expected:
            unexpected += 1
            continue
        expected[name].append(next((child.tag for child in case if child.tag in {"error", "failure", "skipped"}), "passed"))

    # Publish only joint test identities and outcomes. Full suite JUnit can
    # contain tracebacks and fixture values that are unnecessary as evidence.
    suite = ET.Element("testsuite", name="native-account-joint", tests=str(len(expected)))
    problems = []
    totals = {"failure": 0, "error": 0, "skipped": 0}
    for name, statuses in expected.items():
        case = ET.SubElement(suite, "testcase", classname=JOINT_CLASS, name=name)
        if statuses == ["passed"]:
            continue
        status = statuses[0] if len(statuses) == 1 else "error"
        detail = statuses[0] if len(statuses) == 1 else "duplicate" if statuses else "missing"
        ET.SubElement(case, status, message=detail)
        totals[status] += 1
        problems.append(f"{name}: {detail}")
    suite.attrib.update(failures=str(totals["failure"]), errors=str(totals["error"]), skipped=str(totals["skipped"]))
    if evidence is not None:
        ET.ElementTree(suite).write(evidence, encoding="utf-8", xml_declaration=True)
    if unexpected:
        problems.append(f"{unexpected} joint results have no collected node ID")
    if problems:
        raise GateError("joint tests did not all execute and pass:\n" + "\n".join(problems))
    print(f"Verified {len(expected)} collected joint tests executed and passed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("--cargo-json", type=Path, required=True)
    staging.add_argument("--source-sha", required=True)
    staging.add_argument("--output-dir", type=Path, required=True)
    checking = commands.add_parser("verify")
    checking.add_argument("--artifact-dir", type=Path, required=True)
    checking.add_argument("--expected-source-sha", required=True)
    results = commands.add_parser("verify-results")
    results.add_argument("--junit", type=Path, required=True)
    results.add_argument("--expected-nodeids", type=Path, required=True)
    results.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            stage(args.cargo_json, args.source_sha, args.output_dir)
        elif args.command == "verify":
            binary = verify(args.artifact_dir, args.expected_source_sha)
            print(f"Verified operator test: {binary}")
        else:
            verify_results(args.junit, args.expected_nodeids, args.evidence)
    except (GateError, OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f"G1 operator artifact: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
