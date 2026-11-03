#!/usr/bin/env python3
"""Keep the installer operator build covered by an exact CI Clippy feature set.

Requires PyYAML 6.0.3 (already pinned in CI's workflow-lint job). Only literal,
standalone Cargo commands are supported: dynamic flags must fail closed rather
than silently claiming coverage. This checks configuration, not a Windows build.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shlex
import sys
import unittest

try:
    import yaml
except ImportError:
    raise SystemExit("Install the workflow-check dependency: python3 -m pip install pyyaml==6.0.3")

ROOT = Path(__file__).resolve().parents[1]
OPERATOR = "implementation/desktop/crates/selahcue-operator"
INSTALLER = ".github/workflows/windows-installer.yml"


def load(text: str) -> dict:
    # BaseLoader preserves `on` as a key (YAML 1.1 SafeLoader treats it as True).
    data = yaml.load(text, Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError("Expected a workflow mapping")
    return data


def cargo_commands(job: dict, prefix: list[str]) -> list[tuple[list[str], dict]]:
    commands = []
    for step in job.get("steps", []):
        for line in step.get("run", "").splitlines():
            if not line.strip().startswith(" ".join(prefix) + " "):
                continue
            tokens = shlex.split(line, comments=True)
            if tokens[:len(prefix)] == prefix:
                commands.append((tokens, step))
    return commands


def config(tokens: list[str]) -> tuple[frozenset[str], bool]:
    """Parse only the literal feature grammar supported by this gate.

    Tauri's -f/--features consumes multiple unquoted values; Cargo's -F/
    --features consumes one value (which may itself contain spaces or commas).
    Unknown options/operands are refused rather than skipped. This deliberately
    does not attempt to interpret arbitrary shell commands or Cargo passthrough.
    """
    tauri = tokens[:3] == ["cargo", "tauri", "build"]
    if not tauri and tokens[:2] != ["cargo", "clippy"]:
        raise ValueError("Expected cargo tauri build or cargo clippy")
    features: set[str] = set()
    no_default = False
    index = 3 if tauri else 2
    flags = ("--features", "-f") if tauri else ("--features", "-F")
    plain_flags = {"--ci"} if tauri else {"--all-targets", "--release"}
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            if not tauri and tokens[index:] == ["--", "-D", "warnings"]:
                break
            raise ValueError("Unsupported Cargo passthrough or Clippy arguments")
        if token == "--no-default-features":
            no_default = True
            index += 1
            continue
        if token in plain_flags:
            index += 1
            continue
        if token in flags:
            index += 1
            values = []
            if index < len(tokens) and not tokens[index].startswith("-"):
                values.append(tokens[index])
                index += 1
        elif token.startswith("--features="):
            values = [token.split("=", 1)[1]]
            index += 1
        else:
            raise ValueError(f"Unsupported option or operand: {token!r}")
        if tauri:
            while index < len(tokens) and not tokens[index].startswith("-"):
                values.append(tokens[index])
                index += 1
        if not values:
            raise ValueError("Missing feature list")
        for value in values:
            names = value.replace(",", " ").split()
            if not names or any(not name.replace("-", "").replace("_", "").isalnum() for name in names):
                raise ValueError(f"Unsupported literal feature list: {value!r}")
            features.update(names)
    return frozenset(features), no_default


def operator_directory(job: dict, step: dict) -> bool:
    directory = step.get("working-directory", job.get("defaults", {}).get("run", {}).get("working-directory", ""))
    directory = directory.removeprefix("${{ github.workspace }}/").rstrip("/")
    return directory == OPERATOR


def check(ci: dict, installer: dict) -> list[str]:
    problems = []
    build = installer["jobs"]["build"]
    shipped = cargo_commands(build, ["cargo", "tauri", "build"])
    if len(shipped) != 1 or not operator_directory(build, shipped[0][1]):
        return ["Expected exactly one literal operator cargo tauri build command in installer"]
    wanted = config(shipped[0][0])
    native = ci["jobs"]["operator-native"]
    linted = []
    for tokens, step in cargo_commands(native, ["cargo", "clippy"]):
        # A disabled/conditional lint does not cover a push. These are the existing
        # normal gate spellings; unsupported conditions require an explicit review.
        if step.get("if", "") not in ("", "${{ !cancelled() }}", "!cancelled()"):
            continue
        if operator_directory(native, step) and "--all-targets" in tokens and tokens[-3:] == ["--", "-D", "warnings"]:
            linted.append(config(tokens))
    if wanted not in linted:
        problems.append(f"Installer features/defaults {wanted} have no exact operator-native Clippy match: {linted}")
    filter_steps = [s for s in ci["jobs"]["changes"]["steps"] if s.get("id") == "filter"]
    if len(filter_steps) != 1:
        problems.append("Expected one changes/filter step")
    else:
        filters = load(filter_steps[0].get("with", {}).get("filters", ""))
        if INSTALLER not in filters.get("desktop", []):
            problems.append(f"Installer-only PR does not match desktop filter: add {INSTALLER}")
    return problems


def read_workflows(root: Path) -> tuple[dict, dict]:
    return load((root / ".github/workflows/ci.yml").read_text()), load((root / INSTALLER).read_text())


class Controls(unittest.TestCase):
    def setUp(self) -> None:
        # Independent fixture: an unpatched repository must fail the live check,
        # while these controls still describe a valid configuration.
        self.ci = load("""
jobs:
  changes:
    steps:
      - id: filter
        with:
          filters: |
            desktop:
              - '.github/workflows/windows-installer.yml'
  operator-native:
    defaults:
      run:
        working-directory: implementation/desktop/crates/selahcue-operator
    steps:
      - run: cargo clippy --features stt --all-targets -- -D warnings
        if: ${{ !cancelled() }}
""")
        self.installer = load("""
jobs:
  build:
    steps:
      - run: cargo tauri build --features stt
        working-directory: implementation/desktop/crates/selahcue-operator
""")

    def test_matching(self) -> None:
        self.assertEqual(check(self.ci, self.installer), [])

    def test_feature_drift_fails(self) -> None:
        self.installer["jobs"]["build"]["steps"][0]["run"] += ",cloud-stt"
        self.assertTrue(check(self.ci, self.installer))

    def test_tauri_variadic_feature_drift(self) -> None:
        for arguments in ('--features stt openai-notes',
                          '--features "stt openai-notes"',
                          '--features stt,openai-notes',
                          '--features=stt openai-notes',
                          '-f stt openai-notes'):
            with self.subTest(arguments=arguments):
                self.installer["jobs"]["build"]["steps"][0]["run"] = "cargo tauri build " + arguments
                self.assertTrue(check(self.ci, self.installer))

    def test_tauri_variadic_equivalence_and_defaults(self) -> None:
        expected = (frozenset({"stt", "openai-notes"}), False)
        lint = self.ci["jobs"]["operator-native"]["steps"][0]
        lint["run"] = "cargo clippy --features stt,openai-notes --all-targets -- -D warnings"
        for arguments in ('--features stt openai-notes',
                          '--features "stt openai-notes"',
                          '--features stt,openai-notes',
                          '--features=stt,openai-notes',
                          '-f stt openai-notes --ci'):
            with self.subTest(arguments=arguments):
                command = "cargo tauri build " + arguments
                self.assertEqual(config(shlex.split(command)), expected)
                self.installer["jobs"]["build"]["steps"][0]["run"] = command
                self.assertEqual(check(self.ci, self.installer), [])
                self.installer["jobs"]["build"]["steps"][0]["run"] += " --no-default-features"
                self.assertTrue(check(self.ci, self.installer))

    def test_cargo_does_not_consume_unquoted_variadic_features(self) -> None:
        with self.assertRaises(ValueError):
            config(shlex.split("cargo clippy --features stt openai-notes --all-targets -- -D warnings"))
        self.assertEqual(config(shlex.split('cargo clippy -F "stt openai-notes" --all-targets -- -D warnings')),
                         (frozenset({"stt", "openai-notes"}), False))

    def test_superset_is_not_exact(self) -> None:
        self.ci["jobs"]["operator-native"]["steps"][0]["run"] = "cargo clippy --features stt,cloud-stt --all-targets -- -D warnings"
        self.assertTrue(check(self.ci, self.installer))

    def test_default_feature_drift(self) -> None:
        self.installer["jobs"]["build"]["steps"][0]["run"] += " --no-default-features"
        self.assertTrue(check(self.ci, self.installer))

    def test_missing_path_fails(self) -> None:
        self.ci["jobs"]["changes"]["steps"][0]["with"]["filters"] = "desktop: ['implementation/desktop/**']"
        self.assertTrue(check(self.ci, self.installer))

    def test_comment_is_not_a_command(self) -> None:
        step = self.ci["jobs"]["operator-native"]["steps"][0]
        step["run"] = "# " + step["run"]
        self.assertTrue(check(self.ci, self.installer))

    def test_wrong_crate_or_disabled_lint(self) -> None:
        for change in ({"working-directory": "implementation/desktop"}, {"if": "false"}):
            ci = copy.deepcopy(self.ci)
            ci["jobs"]["operator-native"]["steps"][0].update(change)
            self.assertTrue(check(ci, self.installer))

    def test_missing_build_fails(self) -> None:
        self.installer["jobs"]["build"]["steps"] = []
        self.assertTrue(check(self.ci, self.installer))

    def test_feature_syntax(self) -> None:
        self.assertEqual(config(shlex.split('cargo clippy --features "b a,b"')), config(shlex.split("cargo clippy --features=a,b")))
        for text in ("cargo clippy --features $FEATURES", "cargo clippy --all-features", "cargo clippy --features", "cargo clippy -p unrelated --features stt"):
            with self.assertRaises(ValueError):
                config(shlex.split(text))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        return 0 if result.wasSuccessful() else 1
    try:
        problems = check(*read_workflows(args.root))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"installer feature parity: invalid workflow: {exc}", file=sys.stderr)
        return 1
    if problems:
        for problem in problems:
            print(f"installer feature parity: {problem}", file=sys.stderr)
        return 1
    print("installer feature parity: exact operator-native lint match; installer-only desktop path covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
