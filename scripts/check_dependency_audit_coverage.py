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

DERIVATION -- TWO ROUNDS OF THE SAME LESSON (security review, Sana, PR #105, both BLOCKING).

Round 1: the first cut of this script read the required set off
`implementation/desktop/Cargo.toml`'s own `exclude = [...]` list, reasoning it was "a genuine,
independent, already-must-exist source of truth". It is not, in THIS repo: `members` is an
explicit list of paths, not a glob, so `exclude` is not load-bearing for keeping
`selahcue-operator`/`selahcue-stt` out of the workspace -- proven directly by removing
`selahcue-stt` from `exclude` and running `cargo metadata` at the workspace root: exit 0, no
warning, `selahcue-stt` still absent from the package list, because it was never a member to begin
with. A future crate could get its own `Cargo.lock` and never touch `exclude` at all.

Round 2: the fix for round 1 scanned for a top-level `[workspace]` table in each nested
`Cargo.toml` instead -- Cargo's own marker for "this is meant to be its own root". Still wrong,
proven again with a scratch workspace: a nested crate with a PLAIN `[package]` manifest and no
`[workspace]` table of its own is STILL its own independent Cargo root with its own `Cargo.lock`
the moment nothing in the parent's `members` list references it -- `cargo generate-lockfile`
inside it succeeds and writes a `Cargo.lock` the parent's `cargo audit` never sees. `[workspace]`
is a SUFFICIENT signal that a directory is a deliberate root (and this repo's own two extra roots
both use it, by convention -- see their own comments), but it is not a NECESSARY one, and a
regex matching only the bare `^[workspace]` line also missed a `[workspace.package]`-only table
and a trailing inline comment on the same line.

What actually decides whether `cargo audit` needs a dedicated step for a directory is simpler than
either of the above: **does `Cargo.lock` exist there.** That is the literal artefact `cargo audit`
reads, not an inference about which Cargo.toml table a human remembered to write. This script's
primary source of truth is now a walk for every `Cargo.lock` in the repo (excluding `target/` and
`.git/`, which can contain vendored/generated or historical copies that are not real project
roots). Applied to the real repo this yields exactly the three real roots (all git-tracked, none
`.gitignore`d): `implementation/desktop`, `implementation/desktop/crates/selahcue-operator`,
`implementation/desktop/crates/selahcue-stt`.

The `[workspace]`/`[workspace.package]` table scan is kept as a secondary, UNIONED-IN source, not
because it is reliable on its own, but because it catches a crate one step EARLIER than the
lockfile scan can: a freshly created crate that declares its own workspace table but has not yet
had `cargo` run against it (no `Cargo.lock` on disk yet) would otherwise stay invisible to this
check until someone happens to build it once. The union costs nothing when the two agree (today,
they agree exactly) and only ever widens the required set, never narrows it.

The walk root is the repository root, not `implementation/desktop/` -- the earlier version only
walked the desktop tree while its own docstring claimed "every Cargo root in this repo"; nothing
else in the repo is Rust today, but a future Rust helper anywhere else (`implementation/api`, a
top-level tool) would otherwise be silently out of scope for this check by construction.

Self-test: `check_dependency_audit_coverage.py --self-test` exercises both discovery functions
against real temporary-directory fixtures (including the exact "own Cargo.lock, no `[workspace]`
table at all" case Sana's second finding hinged on, and the `[workspace.package]`-only / trailing-
comment spellings her review also caught) and the ci.yml parsing/comparison logic against small
text fixtures, so all of it is trusted before this is pointed at the repo.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Directory name components that are never a real project root: build output and VCS internals.
_IGNORED_DIR_PARTS = {"target", ".git"}

# Matches a top-level (2-space-indented) job key, e.g. "  audit:" or "  supply-chain:". Used to
# find where the `audit` job's body ends: the next line at this indent after `  audit:` itself.
_JOB_KEY_RE = re.compile(r"^  [A-Za-z0-9_-]+:\s*$", re.MULTILINE)

# A step's `- name:`/`- uses:` opening line, at the 6-space indent GitHub Actions step lists use
# in this file's style. Used to split a job's `steps:` body into individual step blocks.
_STEP_START_RE = re.compile(r"^      - ", re.MULTILINE)

_RUN_CARGO_AUDIT_RE = re.compile(r"run:\s*cargo audit\b")
_WORKING_DIR_RE = re.compile(r"working-directory:\s*(\S+)")

# Tolerant of inner spacing (`[ workspace ]`), a trailing inline comment, and the
# `[workspace.package]`-only spelling that still makes a manifest its own workspace root even
# with no bare `[workspace]` line (both gaps Sana's review found in the previous version's
# `^\[workspace\]\s*$` regex).
_WORKSPACE_TABLE_RE = re.compile(r"^\[\s*workspace(?:\.\w+)?\s*\]\s*(?:#.*)?$", re.MULTILINE)


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


def _is_ignored(rel_path: Path) -> bool:
    return any(part in _IGNORED_DIR_PARTS for part in rel_path.parts)


def discover_lockfile_roots(repo_root: Path) -> set[str]:
    """Return every directory (as a posix path relative to `repo_root`, "." for the root
    itself) containing a `Cargo.lock` -- the literal artefact `cargo audit` reads. This is the
    PRIMARY source of truth: see DERIVATION in the module docstring for why inferring
    "independent root" from Cargo.toml table markers (this script's own previous approach,
    twice) is not sufficient on its own."""
    roots: set[str] = set()
    for lockfile in repo_root.rglob("Cargo.lock"):
        if not lockfile.is_file():
            # A directory literally named "Cargo.lock" would otherwise reach the caller as a
            # root with no real lockfile behind it -- vanishingly unlikely, but cheap to guard
            # (code review, Cody, PR #105).
            continue
        rel_dir = lockfile.parent.relative_to(repo_root)
        if _is_ignored(rel_dir):
            continue
        roots.add(rel_dir.as_posix())
    return roots


def discover_workspace_table_roots(repo_root: Path) -> set[str]:
    """Return every directory (as a posix path relative to `repo_root`, "." for the root
    itself) whose own `Cargo.toml` declares a workspace-table marker (`[workspace]` or
    `[workspace.package]`, tolerant of spacing and a trailing comment). SECONDARY source, unioned
    with `discover_lockfile_roots`: it catches a crate one step earlier -- before `cargo` has ever
    been run against it and produced a `Cargo.lock` -- not instead of the lockfile scan, which
    Sana's review proved is the only source that can't itself be true-but-incomplete."""
    roots: set[str] = set()
    for cargo_toml in repo_root.rglob("Cargo.toml"):
        if not cargo_toml.is_file():
            # A directory literally named "Cargo.toml" would otherwise crash `.read_text()`
            # with a raw IsADirectoryError instead of a clean message (code review, Cody,
            # PR #105 -- found while auditing this exact read for the equivalent gap).
            continue
        rel_dir = cargo_toml.parent.relative_to(repo_root)
        if _is_ignored(rel_dir):
            continue
        if _WORKSPACE_TABLE_RE.search(cargo_toml.read_text()):
            roots.add(rel_dir.as_posix())
    return roots


def discover_required_roots(repo_root: Path) -> set[str]:
    """The full required-audit-root set: every `Cargo.lock` location, unioned with every
    workspace-table location, relative to `repo_root`."""
    return discover_lockfile_roots(repo_root) | discover_workspace_table_roots(repo_root)


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
            "Cargo root(s) with their own `Cargo.lock` (or their own workspace-table marker) and "
            f"NO `cargo audit` step in the `dependency audit (RustSec)` job: {sorted(missing)}. "
            "Add a step matching the existing 'Audit desktop workspace' / 'Audit operator shell' "
            "pattern, with `working-directory` set to the missing root."
        )
    extra = covered - required_roots
    if extra:
        problems.append(
            "`cargo audit` step(s) with a `working-directory` that has neither its own "
            f"`Cargo.lock` nor its own workspace-table marker on disk: {sorted(extra)}. Either "
            "the crate rejoined the default workspace (drop its dedicated step) or its "
            "`Cargo.lock`/`[workspace]` table is missing (restore it, or drop the step) -- this "
            "script can't tell which, but the two have drifted apart and someone needs to look."
        )
    return problems


def _write(root: Path, rel_path: str, filename: str, text: str) -> None:
    root.joinpath(rel_path).mkdir(parents=True, exist_ok=True)
    root.joinpath(rel_path, filename).write_text(text)


def self_test() -> int:
    # --- discovery functions: real filesystem fixtures, no dependency on the real repo ---
    with tempfile.TemporaryDirectory() as tmp:
        fixture_root = Path(tmp)

        # Root workspace: has both its own Cargo.lock and a [workspace] table.
        _write(fixture_root, ".", "Cargo.toml", "[workspace]\nmembers = [\"crates/plain-member\"]\n")
        _write(fixture_root, ".", "Cargo.lock", "# root lockfile\n")

        # A regular member: no Cargo.lock of its own, no workspace table -- not a root.
        _write(fixture_root, "crates/plain-member", "Cargo.toml", '[package]\nname = "plain"\n')

        # Sana's second BLOCKING finding, reproduced directly: an independent root with its own
        # Cargo.lock but a PLAIN [package] manifest -- no [workspace] table anywhere. The
        # lockfile-based scan must still find it; the table-based scan (on its own) would not.
        _write(
            fixture_root,
            "crates/independent-no-workspace-table",
            "Cargo.toml",
            '[package]\nname = "independent"\n',
        )
        _write(fixture_root, "crates/independent-no-workspace-table", "Cargo.lock", "# lockfile\n")

        # A freshly created crate with its own [workspace] table but no Cargo.lock yet (nobody
        # has built it). Only the table scan finds this one -- the whole reason it's unioned in.
        _write(
            fixture_root,
            "crates/not-yet-built",
            "Cargo.toml",
            "[workspace]\n\n[package]\nname = \"not-yet-built\"\n",
        )

        # Spelling variants Sana's review flagged as missed by the previous `^\[workspace\]\s*$`
        # regex: inner spacing + a trailing comment, and a `[workspace.package]`-only table.
        _write(
            fixture_root,
            "crates/spaced-with-comment",
            "Cargo.toml",
            '[ workspace ]  # own root, see ADR-0019\n\n[package]\nname = "spaced"\n',
        )
        _write(
            fixture_root,
            "crates/workspace-package-only",
            "Cargo.toml",
            '[workspace.package]\nversion = "0.1.0"\n\n[package]\nname = "wpo"\n',
        )

        # Must never count: a build-output directory and a VCS-internal one.
        _write(fixture_root, "target/debug/build/some-dep", "Cargo.lock", "# not a real root\n")
        _write(fixture_root, ".git/modules/foo", "Cargo.lock", "# not a real root\n")

        # A directory literally named "Cargo.toml"/"Cargo.lock" must not crash `.read_text()`
        # with a raw IsADirectoryError (Cody, PR #105 re-review: found the missing `is_file()`
        # guard while auditing the previous version's fixture, which had a typo that meant it
        # never actually exercised this path).
        fixture_root.joinpath("crates/weird-dir-name/Cargo.toml").mkdir(parents=True)
        fixture_root.joinpath("crates/weird-dir-name/Cargo.lock").mkdir(parents=True)

        lockfile_roots = discover_lockfile_roots(fixture_root)
        assert lockfile_roots == {".", "crates/independent-no-workspace-table"}, lockfile_roots

        table_roots = discover_workspace_table_roots(fixture_root)
        assert table_roots == {
            ".",
            "crates/not-yet-built",
            "crates/spaced-with-comment",
            "crates/workspace-package-only",
        }, table_roots

        required = discover_required_roots(fixture_root)
        assert required == {
            ".",
            "crates/independent-no-workspace-table",
            "crates/not-yet-built",
            "crates/spaced-with-comment",
            "crates/workspace-package-only",
        }, required

    # --- check(): ci.yml text fixtures, required set passed in directly ---
    required = {
        "implementation/desktop",
        "implementation/desktop/crates/selahcue-operator",
        "implementation/desktop/crates/selahcue-stt",
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

    # Reproduce the actual bug this ticket found: selahcue-stt is a required root, but has no
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
    # temporarily disable a check while leaving a note), must NOT be counted as coverage.
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

    # Reverse drift: a stale audit step for a root that is no longer a real Cargo root.
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
        required = discover_required_roots(REPO_ROOT)
        problems = check(required, CI_WORKFLOW.read_text())
    except CoverageError as exc:
        print(f"check_dependency_audit_coverage: {exc}", file=sys.stderr)
        return 1

    if problems:
        print(
            "check_dependency_audit_coverage: the dependency-audit job's coverage has drifted "
            "from the Cargo roots actually on disk:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("check_dependency_audit_coverage: every Cargo root with its own Cargo.lock has a matching audit step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
