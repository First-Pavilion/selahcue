"""Resolve and build the scratch adapter against the frozen owning native source tree."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".native-target"
TARGET = WORK / "cargo-target"
HOME = WORK / "cargo-home"
BINARY = TARGET / "debug" / "coverage-native-golden"
EVIDENCE = ROOT / "fixtures" / "native"
SOURCE = Path("/Users/m.oluwole/.codex/worktrees/selahcue-provider-qualification/scph")
TOOLCHAIN = Path("/Users/m.oluwole/.rustup/toolchains/1.98.0-aarch64-apple-darwin/bin")
REGISTRY = Path("/Users/m.oluwole/.cargo/registry")
PIN = Path("/private/tmp/selahcue-notes-native-input-pin-20261115.json")
PIN_HASH = "f3f6dbb0f33098d5e723701c3d1cdb7f0f9f157242fb0bd55a47b434d06b864f"
NORMATIVE = "1ea22e1ce6e52ab8aa2e0fd83fda1c9d90b094da"
LOCK = Path("implementation/desktop/Cargo.lock")
SPEC_HASH = "e27c305d911e5087539666087d299b15af52ea70aeadb9a9b1fba122bc5d85bd"
ORIGINAL_SPEC = Path("/private/tmp/selahcue-notes-coverage-spec-20261114.md")
SCOPE = (
    "implementation/desktop/crates/selahcue-core",
    "implementation/desktop/crates/selahcue-cloud",
    "implementation/desktop/crates/selahcue-scripture",
    str(LOCK), "implementation/desktop/Cargo.toml", "rust-toolchain.toml",
)
ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "HOME": str(WORK / "empty-home"),
    "TMPDIR": str(WORK / "tmp"),
    "CARGO_HOME": str(HOME),
    "CARGO_TARGET_DIR": str(TARGET),
    "CARGO_NET_OFFLINE": "true",
    "RUSTC": str(TOOLCHAIN / "rustc"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
}


def digest(path):
    with path.open("rb") as reader:
        return sha256(reader.read()).hexdigest()


def command(*args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, capture_output=True, env=ENV)
    if result.stderr:
        print(result.stderr.decode(), end="", file=sys.stderr)
    result.check_returncode()
    return result.stdout


def origin():
    assert digest(PIN) == PIN_HASH
    receipt = json.loads(PIN.read_bytes())
    assert receipt["normative_native_commit"] == NORMATIVE
    assert Path(receipt["source_root"]) == SOURCE
    pins = receipt["file_sha256"]
    tracked = command("/usr/bin/git", "ls-tree", "-r", "--name-only", NORMATIVE, "--", *SCOPE, cwd=SOURCE)
    assert len(pins) == 102 and set(tracked.decode().splitlines()) == set(pins)
    for relative, expected in pins.items():
        path = SOURCE / relative
        assert path.is_file() and not path.is_symlink() and digest(path) == expected, relative
    command("/usr/bin/git", "diff", "--exit-code", NORMATIVE, "--", *SCOPE, cwd=SOURCE)
    assert not command("/usr/bin/git", "ls-files", "--others", "--", *SCOPE, cwd=SOURCE)
    assert digest(ROOT / "docs/superpowers/specs/coverage-v1.md") == digest(ORIGINAL_SPEC) == SPEC_HASH
    return {
        "checkout_head": command("/usr/bin/git", "rev-parse", "HEAD", cwd=SOURCE).decode().strip(),
        "normative_commit": NORMATIVE,
        "source_root": str(SOURCE),
        "pin_receipt_sha256": PIN_HASH,
        "file_sha256": pins,
    }


def registry_tuples(lock):
    return {
        (p["name"], p["version"], p["source"], p["checksum"])
        for p in tomllib.loads(lock.read_text())["package"] if "source" in p
    }


def seed_cache():
    (HOME / "registry").mkdir(parents=True, exist_ok=True)
    for cache in ("cache", "index", "src"):
        target = HOME / "registry" / cache
        if not target.exists():
            command("/bin/cp", "-cR", REGISTRY / cache, target)


def cargo(*args):
    return command(TOOLCHAIN / "cargo", *args, "--manifest-path", ROOT / "native-golden/Cargo.toml")


def build(resolve):
    before = origin()
    scratch_lock = ROOT / "native-golden/Cargo.lock"
    seed_cache()
    if resolve:
        assert not scratch_lock.exists()
        shutil.copyfile(SOURCE / LOCK, scratch_lock)
    mode = "--offline" if resolve else "--frozen"
    metadata = json.loads(cargo("metadata", mode, "--format-version", "1"))
    features_by_package = {node["id"]: node["features"] for node in metadata["resolve"]["nodes"]}
    local = {
        package["name"]: features_by_package[package["id"]]
        for package in metadata["packages"] if package["source"] is None
    }
    assert local == {"coverage-native-golden": [], "selahcue-cloud": ["openai"],
                     "selahcue-core": [], "selahcue-scripture": []}
    registry = registry_tuples(scratch_lock)
    assert registry and registry <= registry_tuples(SOURCE / LOCK)
    lock_digest = digest(scratch_lock)
    cargo("build", "--frozen", "--target-dir", TARGET, "--jobs", "2")
    features = cargo("tree", "--frozen", "--edges", "features")
    assert digest(scratch_lock) == lock_digest
    assert before["file_sha256"] == origin()["file_sha256"]
    evidence = compiled_evidence()
    evidence["before_build"] = before
    evidence["after_build"] = origin()
    evidence["cargo_version"] = command(TOOLCHAIN / "cargo", "--version").decode().strip()
    evidence["rustc_version"] = command(TOOLCHAIN / "rustc", "--version").decode().strip()
    evidence["registry_tuples"] = sorted(registry)
    evidence["local_features"] = local
    evidence["owning_lock_sha256"] = digest(SOURCE / LOCK)
    evidence["every_registry_tuple_matches_owning_lock"] = True
    (EVIDENCE / "feature-tree.txt").write_bytes(features)
    (EVIDENCE / "build.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def compiled_evidence():
    inputs = {}
    generated = {}
    native = origin()
    for crate in ("core", "cloud", "scripture"):
        paths = sorted((TARGET / "debug/deps").glob(f"selahcue_{crate}-*.d"))
        assert len(paths) == 1, paths
        info = paths[0].read_text()
        input_paths = info.splitlines()[0].split(": ", 1)[1].split()
        existing = set()
        for value in input_paths:
            path = Path(value).resolve(strict=True)
            if path.is_relative_to(TARGET):
                assert crate == "scripture" and path.name == "verse_runs.rs", path
                generated[str(path)] = digest(path)
                existing.add(str(path))
            else:
                relative = path.relative_to(SOURCE).as_posix()
                assert relative in native["file_sha256"], value
                existing.add(relative)
        assert f"implementation/desktop/crates/selahcue-{crate}/src/lib.rs" in existing
        inputs[crate] = {"dep_info_sha256": digest(paths[0]), "paths": sorted(existing)}
    build_scripts = sorted((TARGET / "debug/build").glob("selahcue-scripture-*/build_script_build-*.d"))
    assert len(build_scripts) == 1
    assert str(SOURCE / "implementation/desktop/crates/selahcue-scripture/build.rs") in build_scripts[0].read_text()
    rerun = sorted((TARGET / "debug/build").glob("selahcue-scripture-*/output"))
    assert len(rerun) == 1
    scripture = SOURCE / "implementation/desktop/crates/selahcue-scripture"
    build_inputs = []
    for line in rerun[0].read_text().splitlines():
        prefix = "cargo:rerun-if-changed="
        assert line.startswith(prefix), line
        path = (scripture / line.removeprefix(prefix)).resolve(strict=True)
        relative = path.relative_to(SOURCE).as_posix()
        assert relative in native["file_sha256"], relative
        build_inputs.append(relative)
    return {
        "scripture_build_inputs": sorted(build_inputs),
        "generated_file_sha256": generated,
        "harness_input_sha256": {
            path: digest(ROOT / path) for path in ("native-golden/Cargo.toml", "native-golden/src/main.rs")
        },
        "binary_path": str(BINARY),
        "binary_sha256": digest(BINARY),
        "lock_sha256": digest(ROOT / "native-golden/Cargo.lock"),
        "dep_info": inputs,
        "scripture_build_dep_info_sha256": digest(build_scripts[0]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true", help="seed the isolated cache and resolve the scratch lock once")
    parser.add_argument("--verify", action="store_true", help="verify current provenance and the compiled binary only")
    args = parser.parse_args()
    for path in (Path(ENV["HOME"]), Path(ENV["TMPDIR"])):
        path.mkdir(parents=True, exist_ok=True)
    if args.verify:
        recorded = json.loads((EVIDENCE / "build.json").read_bytes())
        for key, value in compiled_evidence().items():
            assert recorded[key] == value, key
        print(json.dumps({"checkout_head": origin()["checkout_head"], "binary_sha256": digest(BINARY)}))
    else:
        build(args.resolve)
