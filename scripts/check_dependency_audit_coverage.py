#!/usr/bin/env python3
"""Guards 86akmdkdn: `.github/workflows/ci.yml`'s `dependency audit (RustSec)` job must run
`cargo audit` against every Cargo root in this repo, not just whichever roots someone remembered
to add a step for.

This is the THIRD time this repo has been bitten by the same bug class -- a hand-maintained list
of "the crate roots that matter" quietly drifting out of sync with reality while every gate that
reads the stale list keeps printing green:

  1. 86akc2kmh -- `selahcue-operator`'s gitignored sidecar/NDI binaries: a fresh worktree had
     neither file and every Make target touching that crate died before reaching any real gate.
  2. 86akd10dq / 86akby7th -- `check_launch_reachability.py`'s `REQUIRED_DEFAULT_FEATURES` set
     was hardcoded and predated `cloud-stt`, so that feature shipped exactly as unreachable from
     `make launch` as the bug the script exists to catch, with the script still passing.
  3. 86akmdkdn (this script) -- the `dependency audit (RustSec)` job ran `cargo audit` against
     exactly two roots (`implementation/desktop`, `implementation/desktop/crates/selahcue-operator`)
     and never against `implementation/desktop/crates/selahcue-stt` -- also its own excluded Cargo
     root, with its own `Cargo.lock`, reachable from the network via `ureq` (ADR-0019's
     download-on-demand model fetch). PR #39's rustls CVE bump only touched the two audited
     lockfiles; `selahcue-stt/Cargo.lock` kept the vulnerable `rustls 0.23.43` (RUSTSEC-2026-0285)
     on `main`, undetected, until the PR #41 hotfix.

Unlike `check_launch_reachability.py`'s `CRATE_MANIFESTS` (deliberately hardcoded there, with its
own drift check against the Makefile -- see that script's MULTI-CRATE SCOPE section for why a
fully independent source doesn't exist for "which crates `make launch` builds directly"), this
check's job is easier: the workspace's own `exclude = [...]` list in
`implementation/desktop/Cargo.toml` IS a genuine, independent, already-must-exist source of truth
for "which Cargo roots are NOT part of the default workspace and therefore need their own
`cargo audit` step" -- reading it does not require reading the CI job this script exists to
check. So this script derives the required set from that list instead of hardcoding it, and then
asserts every required root has a matching `working-directory:` on a `cargo audit` step inside the
`audit` job of `.github/workflows/ci.yml`. A future fourth excluded root gets audited automatically
the moment someone adds it to `exclude = [...]` -- if they forget the matching CI step, this
fails loudly instead of silently, closing the actual gap rather than just moving it one hop over.

Self-test: `check_dependency_audit_coverage.py --self-test` exercises the parsing/comparison logic
against small fixtures (a passing one and two failing ones) with no dependency on the real
Cargo.toml or ci.yml, so the comparison logic itself is trusted before it is pointed at the repo.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_CARGO_TOML = REPO_ROOT / "implementation" / "desktop" / "Cargo.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The main workspace itself always needs its own audit step -- it is never in `exclude`, since
# `exclude` only lists roots the workspace does NOT fold in.
MAIN_WORKSPACE_ROOT = "implementation/desktop"

# Matches a top-level (2-space-indented) job key, e.g. "  audit:" or "  supply-chain:". Used to
# find where the `audit` job's body ends: the next line at this indent after `  audit:` itself.
_JOB_KEY_RE = re.compile(r"^  [A-Za-z0-9_-]+:\s*$", re.MULTILINE)

# A step's `- name:`/`- uses:` opening line, at the 6-space indent GitHub Actions step lists use
# in this file's style. Used to split a job's `steps:` body into individual step blocks.
_STEP_START_RE = re.compile(r"^      - ", re.MULTILINE)

_RUN_CARGO_AUDIT_RE = re.compile(r"run:\s*cargo audit\b")
_WORKING_DIR_RE = re.compile(r"working-directory:\s*(\S+)")


class CoverageError(Exception):
    """Raised when the two sides can't even be compared (parse failure, not a drift finding)."""


def excluded_crate_roots(cargo_toml_text: str) -> set[str]:
    """Return the `exclude = [...]` paths from a workspace Cargo.toml, prefixed with the main
    workspace's own directory so they read as roots relative to the repo, e.g.
    "implementation/desktop/crates/selahcue-stt"."""
    match = re.search(r"exclude\s*=\s*\[(.*?)\]", cargo_toml_text, re.DOTALL)
    if match is None:
        raise CoverageError(
            f"no `exclude = [...]` list found in {DESKTOP_CARGO_TOML} -- if the workspace no "
            "longer excludes any crate roots, update this script's expectations deliberately "
            "rather than letting it fail closed silently."
        )
    quoted = re.findall(r'"([^"]+)"', match.group(1))
    return {f"{MAIN_WORKSPACE_ROOT}/{path}" for path in quoted}


def audit_job_body(ci_workflow_text: str) -> str:
    """Return the text of the `audit:` job, from its own key up to (not including) the next
    top-level job key."""
    job_start = re.search(r"^  audit:\s*$", ci_workflow_text, re.MULTILINE)
    if job_start is None:
        raise CoverageError(
            f"no `  audit:` job found in {CI_WORKFLOW} -- has the dependency-audit job been "
            "renamed or restructured? Update this script to match."
        )
    rest = ci_workflow_text[job_start.end() :]
    next_job = _JOB_KEY_RE.search(rest)
    return rest[: next_job.start()] if next_job else rest


def audited_roots(job_body: str) -> set[str]:
    """Return the `working-directory` of every step in the job body whose `run:` invokes
    `cargo audit`. A `cargo audit` step with no `working-directory` is a parse error, not a
    silent pass -- this repo's convention is always to set one explicitly for these steps, and an
    implicit repo-root audit would silently skip whichever nested Cargo.lock it was meant to
    cover."""
    roots: set[str] = set()
    starts = [m.start() for m in _STEP_START_RE.finditer(job_body)] + [len(job_body)]
    for start, end in zip(starts, starts[1:]):
        block = job_body[start:end]
        if not _RUN_CARGO_AUDIT_RE.search(block):
            continue
        working_dir = _WORKING_DIR_RE.search(block)
        if working_dir is None:
            raise CoverageError(
                "a `cargo audit` step in the `audit` job has no `working-directory:` -- add one "
                "(this script cannot tell which Cargo root it was meant to cover without it):\n"
                f"{block.strip()}"
            )
        roots.add(working_dir.group(1))
    return roots


def check(cargo_toml_text: str, ci_workflow_text: str) -> list[str]:
    """Return a list of human-readable problems; empty means coverage is complete."""
    required = excluded_crate_roots(cargo_toml_text) | {MAIN_WORKSPACE_ROOT}
    covered = audited_roots(audit_job_body(ci_workflow_text))

    problems: list[str] = []
    missing = required - covered
    if missing:
        problems.append(
            "Cargo root(s) excluded from the workspace (or the workspace itself) with NO "
            "`cargo audit` step in the `dependency audit (RustSec)` job: "
            f"{sorted(missing)}. Add a step matching the existing 'Audit desktop workspace' / "
            "'Audit operator shell' pattern, with `working-directory` set to the missing root."
        )
    extra = covered - required
    if extra:
        problems.append(
            "`cargo audit` step(s) with a `working-directory` that is not the main workspace and "
            f"not in `implementation/desktop/Cargo.toml`'s `exclude` list: {sorted(extra)}. "
            "Either the crate rejoined the workspace (drop its dedicated step) or "
            "`exclude = [...]` is stale (update it) -- this script can't tell which, but the two "
            "have drifted apart and someone needs to look."
        )
    return problems


def self_test() -> int:
    passing_cargo_toml = """
[workspace]
members = ["crates/*"]
exclude = ["crates/selahcue-operator", "crates/selahcue-stt"]
"""
    passing_ci = """
  audit:
    name: dependency audit (RustSec)
    steps:
      - uses: actions/checkout@v4
      - name: Audit desktop workspace
        working-directory: implementation/desktop
        run: cargo audit
      - name: Audit operator shell
        working-directory: implementation/desktop/crates/selahcue-operator
        run: cargo audit
      - name: Audit STT crate
        working-directory: implementation/desktop/crates/selahcue-stt
        run: cargo audit

  supply-chain:
    name: supply chain (licenses + SBOM)
"""
    problems = check(passing_cargo_toml, passing_ci)
    assert problems == [], f"expected no problems on the passing fixture, got: {problems}"

    # Reproduce the actual bug this ticket found: selahcue-stt excluded, but no audit step.
    missing_step_ci = """
  audit:
    name: dependency audit (RustSec)
    steps:
      - uses: actions/checkout@v4
      - name: Audit desktop workspace
        working-directory: implementation/desktop
        run: cargo audit
      - name: Audit operator shell
        working-directory: implementation/desktop/crates/selahcue-operator
        run: cargo audit

  supply-chain:
    name: supply chain (licenses + SBOM)
"""
    problems = check(passing_cargo_toml, missing_step_ci)
    assert len(problems) == 1, f"expected exactly one problem, got: {problems}"
    assert "implementation/desktop/crates/selahcue-stt" in problems[0], problems

    # A step with no working-directory must be a hard parse error, not a silent skip.
    no_working_dir_ci = """
  audit:
    name: dependency audit (RustSec)
    steps:
      - name: Audit desktop workspace
        run: cargo audit

  supply-chain:
    name: supply chain (licenses + SBOM)
"""
    try:
        check(passing_cargo_toml, no_working_dir_ci)
    except CoverageError:
        pass
    else:
        raise AssertionError("expected CoverageError for a cargo-audit step with no working-directory")

    print("check_dependency_audit_coverage: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    try:
        problems = check(DESKTOP_CARGO_TOML.read_text(), CI_WORKFLOW.read_text())
    except CoverageError as exc:
        print(f"check_dependency_audit_coverage: {exc}", file=sys.stderr)
        return 1

    if problems:
        print(
            "check_dependency_audit_coverage: the dependency-audit job's coverage has drifted "
            "from the workspace's own excluded-root list:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("check_dependency_audit_coverage: every excluded Cargo root has a matching audit step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
