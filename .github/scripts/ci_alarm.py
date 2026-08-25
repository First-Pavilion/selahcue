#!/usr/bin/env python3
"""Reconcile the `ci-red` tracking issue for `main`.

WHY THIS IS NOT TWO `if:` CONDITIONS
The first version of this alarm was a pair of jobs: one opened an issue when
something failed, one closed it when nothing had failed. The close condition was
`!contains(needs.*.result,'failure') && !contains(needs.*.result,'cancelled')`,
and **a skipped job is neither**. CI path-filters by area, so an api-only,
marketing-only or mobile-only push to `main` skips the entire desktop matrix and
still satisfies that condition -- it would have closed the issue while `main` was
still broken on `rust`, having verified nothing about `rust` at all.

That is worse than having no alarm, because CLAUDE.md tells readers to treat an
open issue as *the* signal that `main` is broken. An alarm that can lie, next to
documentation saying to trust it, converts "go and look" into "trust a control
that can be wrong".

So the alarm tracks WHICH jobs are outstanding rather than a single red/green
bit, and a job clears itself only by actually reporting success. A skipped job
says nothing, so it changes nothing. The outstanding set lives in the issue body
as an HTML comment, which is the only state this needs.

The reconcile step below is a pure function so it can be tested without GitHub
(`--self-test`); the workflow's first real execution should not be its first
execution ever.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

MARKER = "ci-red-outstanding"
MARKER_RE = re.compile(rf"<!--\s*{MARKER}:\s*([^>]*?)\s*-->")
LABEL = "ci-red"


# --------------------------------------------------------------------------
# Pure logic
# --------------------------------------------------------------------------
def reconcile(outstanding: set[str], results: dict[str, str]) -> tuple[set[str], set[str], set[str]]:
    """Return (new_outstanding, newly_failed, newly_recovered).

    A job leaves the outstanding set ONLY by reporting `success` in this run.
    `skipped` and `cancelled` are not evidence of anything and change nothing --
    that is the whole point of this function.
    """
    newly_failed = {job for job, result in results.items() if result == "failure"}
    newly_recovered = {job for job in outstanding if results.get(job) == "success"}
    new_outstanding = (outstanding - newly_recovered) | newly_failed
    return new_outstanding, newly_failed, newly_recovered


def parse_marker(body: str) -> set[str]:
    match = MARKER_RE.search(body or "")
    if not match:
        return set()
    return {j.strip() for j in match.group(1).split(",") if j.strip()}


def render_marker(outstanding: set[str]) -> str:
    return f"<!-- {MARKER}: {','.join(sorted(outstanding))} -->"


# --------------------------------------------------------------------------
# Self-test — runs anywhere, no GitHub needed
# --------------------------------------------------------------------------
def self_test() -> int:
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")

    # The bug this design exists to prevent: main is red on `rust`; an api-only
    # push skips the whole desktop matrix. The alarm must NOT clear.
    out, failed, rec = reconcile({"rust"}, {"rust": "skipped", "api": "success", "changes": "success"})
    check("skipped job must not clear the alarm", out, {"rust"})
    check("skipped job is not a recovery", rec, set())

    # A real recovery clears it.
    out, _, rec = reconcile({"rust"}, {"rust": "success", "changes": "success"})
    check("success clears the job", out, set())
    check("success is recorded as a recovery", rec, {"rust"})

    # Partial recovery keeps the rest outstanding.
    out, _, _ = reconcile({"rust", "operator"}, {"rust": "success", "operator": "skipped"})
    check("partial recovery keeps the remainder", out, {"operator"})

    # A new failure joins an existing set.
    out, failed, _ = reconcile({"rust"}, {"rust": "success", "flutter": "failure"})
    check("new failure replaces a cleared one", out, {"flutter"})
    check("new failure is reported", failed, {"flutter"})

    # Cancelled is not success and must not clear.
    out, _, _ = reconcile({"rust"}, {"rust": "cancelled"})
    check("cancelled must not clear the alarm", out, {"rust"})

    # Clean run with nothing outstanding stays clean.
    out, failed, _ = reconcile(set(), {"rust": "success", "api": "skipped"})
    check("clean run stays clean", out, set())
    check("clean run reports no failures", failed, set())

    # Marker round-trip, including the empty and malformed cases.
    check("marker round-trip", parse_marker(render_marker({"b", "a"})), {"a", "b"})
    check("absent marker parses empty", parse_marker("no marker here"), set())
    check("empty marker parses empty", parse_marker(f"<!-- {MARKER}:  -->"), set())

    if failures:
        print("ci_alarm self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("ci_alarm self-test: all cases passed")
    return 0


# --------------------------------------------------------------------------
# GitHub side
# --------------------------------------------------------------------------
def gh(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    repo = os.environ["REPO"]
    run_url = os.environ["RUN_URL"]
    sha = os.environ["SHA"][:8]
    results = {job: (data or {}).get("result", "") for job, data in json.loads(os.environ["NEEDS"]).items()}

    gh("label", "create", LABEL, "--repo", repo, "--color", "B60205",
       "--description", "main's pipeline is failing", "--force", check=False)

    found = gh("issue", "list", "--repo", repo, "--label", LABEL, "--state", "open",
               "--limit", "1", "--json", "number,body")
    issues = json.loads(found) if found else []
    issue = issues[0] if issues else None

    outstanding = parse_marker(issue["body"]) if issue else set()
    new_outstanding, newly_failed, newly_recovered = reconcile(outstanding, results)

    verdict = ", ".join(f"{j}={r}" for j, r in sorted(results.items()) if r)
    print(f"this run: {verdict}")
    print(f"outstanding before: {sorted(outstanding) or '-'}")
    print(f"newly failed: {sorted(newly_failed) or '-'} | newly recovered: {sorted(newly_recovered) or '-'}")
    print(f"outstanding after: {sorted(new_outstanding) or '-'}")

    if not new_outstanding:
        if issue:
            gh("issue", "close", str(issue["number"]), "--repo", repo, "--reason", "completed",
               "--comment", f"`main` is green again at `{sha}` — every job that was outstanding has "
                            f"now reported success.\n\nRun: {run_url}")
            print(f"closed issue #{issue['number']}")
        else:
            print("nothing outstanding and no open issue; nothing to do.")
        return 0

    lines = [
        f"`main` has jobs that are failing and have **not** since reported success.",
        "",
        "| job | this run |",
        "|---|---|",
    ]
    for job in sorted(new_outstanding):
        lines.append(f"| `{job}` | {results.get(job) or 'not run'} |")
    lines += [
        "",
        f"Latest commit: `{sha}` · Run: {run_url}",
        "",
        "A job leaves this list only by actually reporting success. A **skipped** job "
        "(CI path-filters by area) is not evidence of anything and does not clear it.",
        "",
        "While this issue is open, treat every branch's CI result as unreadable: a real "
        "failure cannot be told apart from this standing one.",
        "",
        render_marker(new_outstanding),
    ]
    body = "\n".join(lines)

    if issue:
        gh("issue", "edit", str(issue["number"]), "--repo", repo, "--body", body)
        if newly_failed or newly_recovered:
            note = []
            if newly_recovered:
                note.append(f"Recovered: {', '.join(sorted(newly_recovered))}.")
            if newly_failed:
                note.append(f"Now failing: {', '.join(sorted(newly_failed))}.")
            gh("issue", "comment", str(issue["number"]), "--repo", repo,
               "--body", f"{' '.join(note)}\n\nAt `{sha}` · Run: {run_url}")
        print(f"updated issue #{issue['number']}")
    else:
        gh("issue", "create", "--repo", repo, "--label", LABEL,
           "--title", "CI is failing on `main`", "--body", body)
        print("opened a new ci-red issue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
