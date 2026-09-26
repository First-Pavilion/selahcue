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
     and never against `implementation/desktop/crates/selahcue-stt` -- also its own independent
     Cargo root, with its own `Cargo.lock`, reachable from the network via `ureq` (ADR-0019's
     download-on-demand model fetch). PR #39's rustls CVE bump only touched the two audited
     lockfiles; `selahcue-stt/Cargo.lock` kept the vulnerable `rustls 0.23.43` (RUSTSEC-2026-0285)
     on `main`, undetected, until the PR #41 hotfix.

DERIVATION -- WHY THIS SCANS FOR `[workspace]`, NOT `implementation/desktop/Cargo.toml`'s OWN
`exclude = [...]` LIST (security review, Sana, PR #105, BLOCKING). The first cut of this script
read the required set straight off `exclude = [...]`, reasoning it was "a genuine, independent,
already-must-exist source of truth". It is not, in THIS repo: `implementation/desktop/Cargo.toml`'s
`members` is an explicit list of paths, not a glob, and `selahcue-operator`/`selahcue-stt` are not
in it -- which means `exclude` is not load-bearing for keeping either crate out of the workspace;
nothing in Cargo's own behaviour depends on it. Proven directly: removing `selahcue-stt` from
`exclude` and running `cargo metadata` at the workspace root changes nothing -- exit 0, no
warning, and `selahcue-stt` still absent from the package list, because it was never a member to
begin with. So a future crate could declare its own `[workspace]` table, get its own `Cargo.lock`,
and never need to touch `exclude` at all -- this script would have kept reading the stale list and
printed success while that crate's dependencies went unaudited, the exact incident this ticket
exists to close, one hop over.

What IS load-bearing, and is Cargo's own criterion for "this directory is its own Cargo root with
its own `Cargo.lock`, not folded into the parent's": its `Cargo.toml` declares a top-level
`[workspace]` table itself (see `selahcue-operator/Cargo.toml` and `selahcue-stt/Cargo.toml`'s own
comments -- both do this deliberately, "an empty `[workspace]` here makes it its own root"). This
script walks `implementation/desktop/` looking for exactly that marker (skipping `target/`
directories, which can contain vendored/generated manifests that are not real workspace roots).
Applied to the real repo this yields exactly `implementation/desktop`,
`implementation/desktop/crates/selahcue-operator`, `implementation/desktop/crates/selahcue-stt` --
the three real roots, with no dependency on anyone having remembered to edit `exclude = [...]` --
and then asserts each has a matching `working-directory:` on a `cargo audit` step inside the
`audit` job of `.github/workflows/ci.yml`. A future fourth independent root is discovered and
required automatically the moment its own `Cargo.toml` gains a `[workspace]` table; if the CI step
is never added, this fails loudly instead of silently.

Self-test: `check_dependency_audit_coverage.py --self-test` exercises the filesystem discovery
(against real temporary directory fixtures, including the exact case Sana's finding hinged on: a
nested `[workspace]` root with no corresponding `exclude` entry) and the parsing/comparison logic
(against small ci.yml text fixtures) so both halves are trusted before this is pointed at the repo.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = REPO_ROOT / "implementation" / "desktop"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The label the main workspace root is reported under -- matches the `working-directory` the
# existing "Audit desktop workspace" CI step already uses.
MAIN_WORKSPACE_LABEL = "implementation/desktop"

# Matches a top-level (2-space-indented) job key, e.g. "  audit:" or "  supply-chain:". Used to
# find where the `audit` job's body ends: the next line at this indent after `  audit:` itself.
_JOB_KEY_RE = re.compile(r"^  [A-Za-z0-9_-]+:\s*$", re.MULTILINE)

# A step's `- name:`/`- uses:` opening line, at the 6-space indent GitHub Actions step lists use
# in this file's style. Used to split a job's `steps:` body into individual step blocks.
_STEP_START_RE = re.compile(r"^      - ", re.MULTILINE)

_RUN_CARGO_AUDIT_RE = re.compile(r"run:\s*cargo audit\b")
_WORKING_DIR_RE = re.compile(r"working-directory:\s*(\S+)")
_WORKSPACE_TABLE_RE = re.compile(r"^\[workspace\]\s*$", re.MULTILINE)


def _without_full_line_comments(text: str) -> str:
    """Drop every line that is a YAML comment (its stripped text starts with `#`), so a
    leftover `# run: cargo audit` note beside a step that no longer runs it can't be mistaken
    for a live step. Code review (Cody, PR #105) found this as a genuine false-pass: without
    this, disabling a step by commenting out its `run:` line while leaving the old line in
    place as a note kept `audited_roots` reporting the root as covered -- exactly the silent
    drift this script exists to catch, one level down. An inline trailing comment (code then
    `# ...` on the same line) is untouched; only a line that is ENTIRELY a comment is dropped."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


class CoverageError(Exception):
    """Raised when the two sides can't even be compared (parse failure, not a drift finding)."""


def discover_workspace_roots(desktop_root: Path, label: str) -> set[str]:
    """Walk `desktop_root` and return every directory (as `label`, or `label/<relative path>`)
    whose own `Cargo.toml` declares a top-level `[workspace]` table -- the main workspace's own
    `Cargo.toml` included. This is Cargo's own criterion for "this directory is an independent
    Cargo root with its own `Cargo.lock`", not a name someone remembered to add to a separate
    hand-maintained list (see DERIVATION in the module docstring for why the workspace's own
    `exclude = [...]` list is NOT used for this instead)."""
    roots: set[str] = set()
    for cargo_toml in desktop_root.rglob("Cargo.toml"):
        rel_dir = cargo_toml.parent.relative_to(desktop_root)
        if "target" in rel_dir.parts:
            continue
        if _WORKSPACE_TABLE_RE.search(cargo_toml.read_text()):
            roots.add(label if rel_dir == Path(".") else f"{label}/{rel_dir.as_posix()}")
    return roots


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
    job_body = _without_full_line_comments(job_body)
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


def check(required_roots: set[str], ci_workflow_text: str) -> list[str]:
    """Return a list of human-readable problems; empty means coverage is complete."""
    covered = audited_roots(audit_job_body(ci_workflow_text))

    problems: list[str] = []
    missing = required_roots - covered
    if missing:
        problems.append(
            "independent Cargo root(s) (own `[workspace]` table, own `Cargo.lock` -- or the main "
            "workspace itself) with NO `cargo audit` step in the `dependency audit (RustSec)` "
            f"job: {sorted(missing)}. Add a step matching the existing 'Audit desktop workspace' "
            "/ 'Audit operator shell' pattern, with `working-directory` set to the missing root."
        )
    extra = covered - required_roots
    if extra:
        problems.append(
            "`cargo audit` step(s) with a `working-directory` that is not the main workspace and "
            f"has no `[workspace]` table of its own under {DESKTOP_ROOT}: {sorted(extra)}. "
            "Either the crate rejoined the default workspace (drop its dedicated step) or it no "
            "longer declares its own `[workspace]` table (restore it, or drop the step) -- this "
            "script can't tell which, but the two have drifted apart and someone needs to look."
        )
    return problems


def _write_crate(root: Path, rel_path: str, *, own_workspace: bool) -> None:
    root.joinpath(rel_path).mkdir(parents=True, exist_ok=True)
    text = '[package]\nname = "fixture"\n'
    if own_workspace:
        text = "[workspace]\n\n" + text
    root.joinpath(rel_path, "Cargo.toml").write_text(text)


def self_test() -> int:
    # --- discover_workspace_roots: real filesystem fixtures, no dependency on the real repo ---
    with tempfile.TemporaryDirectory() as tmp:
        fixture_root = Path(tmp)
        _write_crate(fixture_root, ".", own_workspace=True)
        _write_crate(fixture_root, "crates/plain-member", own_workspace=False)
        _write_crate(fixture_root, "crates/independent-a", own_workspace=True)
        # The exact scenario Sana's finding hinged on: an independent root with NO entry in any
        # `exclude = [...]` list anywhere (there is no Cargo.toml `exclude` fixture at all here) --
        # discovery must still find it, because it never depended on `exclude` to begin with.
        _write_crate(fixture_root, "crates/independent-b-not-in-any-exclude-list", own_workspace=True)
        # A `target/` directory can contain vendored/generated manifests; these must never count.
        _write_crate(fixture_root, "target/debug/build/some-dep/Cargo.toml", own_workspace=True)

        discovered = discover_workspace_roots(fixture_root, "fixture-root")
        assert discovered == {
            "fixture-root",
            "fixture-root/crates/independent-a",
            "fixture-root/crates/independent-b-not-in-any-exclude-list",
        }, discovered

    # --- check(): ci.yml text fixtures, required set passed in directly ---
    required = {
        MAIN_WORKSPACE_LABEL,
        f"{MAIN_WORKSPACE_LABEL}/crates/selahcue-operator",
        f"{MAIN_WORKSPACE_LABEL}/crates/selahcue-stt",
    }

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
    problems = check(required, passing_ci)
    assert problems == [], f"expected no problems on the passing fixture, got: {problems}"

    # Reproduce the actual bug this ticket found: selahcue-stt is an independent root, but has no
    # audit step.
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
    problems = check(required, missing_step_ci)
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
        check(required, no_working_dir_ci)
    except CoverageError:
        pass
    else:
        raise AssertionError("expected CoverageError for a cargo-audit step with no working-directory")

    # Cody's review of PR #105: a step whose `run:` was changed to something else, but which
    # still has a leftover `# run: cargo audit` comment in the same block (an ordinary way to
    # temporarily disable a check while leaving a note), must NOT be counted as coverage. Before
    # `_without_full_line_comments`, `audited_roots` matched `cargo audit` anywhere in the block
    # text and silently treated this as a passing "Audit STT crate" step.
    disabled_via_comment_ci = """
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
        # run: cargo audit
        run: echo "audit temporarily disabled"

  supply-chain:
    name: supply chain (licenses + SBOM)
"""
    problems = check(required, disabled_via_comment_ci)
    assert len(problems) == 1, (
        f"expected the commented-out STT step to be reported as missing, got: {problems}"
    )
    assert "implementation/desktop/crates/selahcue-stt" in problems[0], problems

    # Reverse drift: a stale audit step for a root that is no longer an independent workspace.
    stale_step_ci = """
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
      - name: Audit a crate that rejoined the workspace
        working-directory: implementation/desktop/crates/selahcue-retired
        run: cargo audit

  supply-chain:
    name: supply chain (licenses + SBOM)
"""
    problems = check(required, stale_step_ci)
    assert len(problems) == 1, f"expected exactly one problem, got: {problems}"
    assert "selahcue-retired" in problems[0], problems

    print("check_dependency_audit_coverage: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    try:
        required = discover_workspace_roots(DESKTOP_ROOT, MAIN_WORKSPACE_LABEL)
        problems = check(required, CI_WORKFLOW.read_text())
    except CoverageError as exc:
        print(f"check_dependency_audit_coverage: {exc}", file=sys.stderr)
        return 1

    if problems:
        print(
            "check_dependency_audit_coverage: the dependency-audit job's coverage has drifted "
            "from the independent Cargo roots actually on disk:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("check_dependency_audit_coverage: every independent Cargo root has a matching audit step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
