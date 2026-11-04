#!/usr/bin/env python3
"""On-disk regression fixtures for the actual workflow-checker CLI (stdlib only)."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

CANONICAL = "${{ github.ref == 'refs/heads/main' }}"


def workflow(event="pull_request", steps=None, uses=None):
    body = f"on: {event}\njobs:\n  build:\n"
    if uses:
        return body + f"    uses: {uses}\n"
    return body + "    runs-on: ubuntu-latest\n    steps:\n" + (steps or "      - uses: Swatinem/rust-cache@v2\n")


def rust(value=None):
    body = "      - uses: Swatinem/rust-cache@v2\n"
    return body if value is None else body + f"        with:\n          save-if: {value}\n"


def cases():
    entry = ".github/workflows/entry.yml"
    called = ".github/workflows/called.yml"
    action = ".github/actions/cache/action.yml"
    for kind, files, needles in (
        ("local reusable", {entry: workflow(uses="./" + called), called: workflow("workflow_call")}, [entry, "build", called, "save-if"]),
        ("local composite", {entry: workflow(steps="      - uses: ./.github/actions/cache\n"), action: "name: cache\nruns:\n  using: composite\n  steps:\n    - uses: Swatinem/rust-cache@v2\n"}, [entry, "build", action, "save-if"]),
        ("nested reusable/composite", {entry: workflow(uses="./" + called), called: workflow("workflow_call", steps="      - uses: ./.github/actions/cache\n"), action: "name: cache\nruns:\n  using: composite\n  steps:\n    - uses: subosito/flutter-action@v2\n      with: {cache: true}\n"}, [entry, called, action, "cache"]),
    ):
        yield kind, files, 1, needles
    yield "guarded local reusable", {entry: workflow(uses="./" + called), called: workflow("workflow_call", rust(CANONICAL))}, 0, []
    yield "guarded nested composite", {entry: workflow(uses="./" + called), called: workflow("workflow_call", steps="      - uses: ./.github/actions/cache\n"), action: "name: cache\nruns:\n  using: composite\n  steps:\n    - uses: Swatinem/rust-cache@v2\n      with:\n        save-if: " + CANONICAL + "\n"}, 0, []
    yield "manual reusable exemption", {entry: workflow("workflow_dispatch", uses="./" + called), called: workflow("workflow_call")}, 0, []
    for event in ("pull_request_target", "workflow_run", "issue_comment"):
        yield event + " ref-only unsafe", {entry: workflow(event, rust(CANONICAL))}, 1, [entry, event, "save-if"]
        yield event + " explicit disabled", {entry: workflow(event, rust("false"))}, 0, []
        yield event + " inherited through call", {entry: workflow(event, uses="./" + called), called: workflow("workflow_call", rust(CANONICAL))}, 1, [entry, called, event]
    yield "ordinary PR explicitly disabled", {entry: workflow(steps=rust("false"))}, 0, []
    for expression in ("${{ (github.ref == 'refs/heads/main') }}", "${{ ((( github.ref == 'refs/heads/main' ))) }}"):
        yield "harmless parentheses " + expression, {entry: workflow(steps=rust(expression))}, 0, []
    for expression in ("${{ (github.ref != 'refs/heads/main') }}", "${{ (github.ref == 'refs/heads/main') || true }}", "${{ (github.ref == 'refs/heads/main') && false }}", "${{ (github.ref_name == 'main') }}", "${{ (github.ref == 'refs/heads/main' }}", "${{ github.ref == 'refs/heads/main') }}"):
        yield "unsafe/unsupported expression " + expression, {entry: workflow(steps=rust(expression))}, 1, ["save-if"]
    yield "action.yaml metadata", {entry: workflow(steps="      - uses: ./.github/actions/cache\n"), ".github/actions/cache/action.yaml": "runs:\n  using: composite\n  steps:\n    - uses: Swatinem/rust-cache@v2\n"}, 1, [entry, "action.yaml", "save-if"]
    yield "local node action is not executed", {entry: workflow(steps="      - uses: ./.github/actions/cache\n"), action: "runs: {using: node24, main: index.js}\n"}, 0, []
    yield "local target is not reusable", {entry: workflow(uses="./" + called), called: workflow("workflow_dispatch", rust(CANONICAL))}, 1, [entry, called, "workflow_call"]
    yield "nested Flutter explicitly disabled", {entry: workflow("issue_comment", steps="      - uses: ./.github/actions/cache\n"), action: "runs:\n  using: composite\n  steps:\n    - uses: subosito/flutter-action@v2\n      with: {cache: false, pub-cache: false}\n"}, 0, []
    deep = {entry: workflow(uses="./.github/workflows/deep0.yml")}
    for index in range(34):
        deep[f".github/workflows/deep{index}.yml"] = workflow("workflow_call", uses=f"./.github/workflows/deep{index + 1}.yml") if index < 33 else workflow("workflow_call", rust(CANONICAL))
    yield "bounded traversal depth", deep, 1, [entry, "bounded depth"]
    yield "missing local reusable", {entry: workflow(uses="./" + called)}, 1, [entry, called]
    yield "missing local action", {entry: workflow(steps="      - uses: ./.github/actions/cache\n")}, 1, [entry, ".github/actions/cache"]
    yield "reusable cycle", {entry: workflow(uses="./" + called), called: workflow("workflow_call", uses="./" + entry)}, 1, [entry, called, "cycle"]
    yield "composite cycle", {entry: workflow(steps="      - uses: ./.github/actions/cache\n"), action: "runs:\n  using: composite\n  steps:\n    - uses: ./.github/actions/cache\n"}, 1, [entry, action, "cycle"]
    yield "local path escape", {entry: workflow(uses="./../outside.yml"), "../outside.yml": workflow("workflow_call", rust(CANONICAL))}, 1, [entry, "outside"]
    yield "malformed top-level YAML", {entry: "on: [pull_request\n"}, 1, [entry, "YAML"]
    yield "malformed reachable YAML", {entry: workflow(uses="./" + called), called: "jobs: [broken\n"}, 1, [entry, called, "YAML"]
    yield "scalar workflow", {entry: "hello\n"}, 1, [entry, "mapping"]
    yield "non-mapping job", {entry: "on: pull_request\njobs: {build: hello}\n"}, 1, [entry, "build", "mapping"]
    yield "non-list composite steps", {entry: workflow(steps="      - uses: ./.github/actions/cache\n"), action: "runs: {using: composite, steps: hello}\n"}, 1, [entry, action, "steps"]


def run_suite(checker):
    checker = Path(checker).resolve()
    failures = []
    count = 0
    for label, files, expected, needles in cases():
        count += 1
        with tempfile.TemporaryDirectory(prefix="workflow-cache-fixture-") as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(checker), ".github/workflows/entry.yml"], cwd=root, capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            if result.returncode != expected or any(needle not in output for needle in needles) or "Traceback" in output:
                failures.append(f"{label}: expected exit{expected} / {needles!r}; got exit{result.returncode}: {output.strip()}")
            if "malformed" in label and expected == 1 and len(output.strip().splitlines()) != 1:
                failures.append(f"{label}: expected one-line diagnostic; got {output.strip()!r}")
    return count, failures


def prove_mutations(checker):
    """Each removed handler must make the committed --self-test gate red."""
    source = Path(checker).read_text()
    mutations = [
        ("reusable traversal removed", "visit_target(reference, label, stack, composite=False)", "pass"),
        ("composite traversal removed", "visit_target(reference, label, stack, composite=True)", "pass"),
        ("pull_request_target detection removed", 'DEFAULT_REF_PR_EVENTS = {"pull_request_target", "workflow_run", "issue_comment"}', 'DEFAULT_REF_PR_EVENTS = {"workflow_run", "issue_comment"}'),
        ("workflow_run detection removed", 'DEFAULT_REF_PR_EVENTS = {"pull_request_target", "workflow_run", "issue_comment"}', 'DEFAULT_REF_PR_EVENTS = {"pull_request_target", "issue_comment"}'),
        ("issue_comment detection removed", 'DEFAULT_REF_PR_EVENTS = {"pull_request_target", "workflow_run", "issue_comment"}', 'DEFAULT_REF_PR_EVENTS = {"pull_request_target", "workflow_run"}'),
        ("parenthesis normalization removed", 'while body.startswith("(") and body.endswith(")"):', "while False:"),
        ("malformed YAML handler removed", "except yaml.YAMLError as error:", "except KeyError as error:"),
        ("cycle detection removed", "if target in stack:", "if False:"),
        ("explicit disabled save handling removed", 'if value.lower() == "false":', "if False:"),
    ]
    for label, old, new in mutations:
        if source.count(old) != 1:
            raise AssertionError(f"{label}: mutation anchor changed; refusing vacuous proof")
        with tempfile.TemporaryDirectory(prefix="workflow-cache-mutant-") as directory:
            root = Path(directory)
            mutant = root / "check_workflows.py"
            mutant.write_text(source.replace(old, new))
            (root / Path(__file__).name).write_text(Path(__file__).read_text())
            result = subprocess.run([sys.executable, str(mutant), "--self-test"], cwd=root,
                                    capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            if result.returncode != 1 or "check_workflows self-test FAILED" not in output:
                raise AssertionError(f"{label}: self-test did not detect actual bypass: {output}")
            print(f"PASS rejected handler mutation: {label}", flush=True)
    return len(mutations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker", default=str(Path(__file__).with_name("check_workflows.py")))
    parser.add_argument("--prove-mutations", action="store_true")
    args = parser.parse_args()
    if args.prove_mutations:
        print(f"workflow cache handler proof: {prove_mutations(args.checker)} mutations caught")
        return 0
    count, failures = run_suite(args.checker)
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"workflow cache CLI fixtures: {count} cases, {len(failures)} failure diagnostics")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
