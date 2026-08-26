#!/usr/bin/env python3
"""Workflow invariants that actionlint does not model.

Two checks, both born from defects that shipped in this branch and were caught by
human review rather than by any gate:

1. TOKEN SCOPES FOR CHECKOUT. Declaring ANY `permissions:` block on a job sets every
   scope NOT listed to `none`. A job written as `permissions: {issues: write}` gets
   `contents: none`, and on a private repository actions/checkout cannot clone: the
   first step fails and everything the job existed to do never runs. The `ci-alarm`
   job shipped exactly that shape -- a permanently dead alarm sitting next to a
   CLAUDE.md telling readers it was the only alarm. actionlint exits 0 on it
   (verified), so nothing else in the pipeline would have caught it.

   SCOPE, stated so nobody over-trusts this: it models ONE scope-consumer, checkout
   needing `contents`. A job that declares `contents: read` and then runs
   `gh issue create` dies the same deny-by-omission death and is NOT detected here.

2. SETUP/GATE ORDERING. Gate steps run under `if: ${{ !cancelled() }}` so one failing
   gate cannot hide the ones after it; setup steps keep the default `success()`,
   because if checkout or the toolchain assertion fails, every later result is
   meaningless. That only holds if all the setup comes FIRST. The operator job had a
   `success()` staging step sitting between two gates, so a formatting failure skipped
   it and the three gates after it then failed on missing placeholders -- one error
   became four red steps, three of them lying about why.

   The rule is purely ordinal -- no step in a job may default to `success()` after any
   step has used `!cancelled()` -- so it is derived from structure, NOT from a
   hand-maintained list of which steps are "setup". An earlier hand-audit exempted the
   offending step by name and therefore validated its own labelling rather than an
   independent property.

Known gaps, so the boundary is written down rather than assumed:
   TODO(86ak5rjh7): a job whose checkout happens inside a remote composite action, a
   reusable-workflow `uses:` call, or a bare `git clone` in a `run:` block is invisible
   to check 1, which matches on `uses: actions/checkout`. None exist in this repo today
   (verified); revisit if one is introduced.

Self-test: `check_workflows.py --self-test`
"""

from __future__ import annotations

import argparse
import glob
import re
import sys

import yaml

CHECKOUT = "actions/checkout"
CONTENTS_OK = {"read", "write"}
NO_CANCEL = "!cancelled()"
# GitHub implies `success() &&` in front of any `if:` that does not itself call a status
# function. So `if: runner.os == 'Linux'` is `success() && runner.os == 'Linux'` and is
# stranded by an earlier gate failure exactly like a step with no `if:` at all. Matching
# on "has no `if:`" would close the spelling and leave the class open.
STATUS_FN = re.compile(r"\b(success|always|failure|cancelled)\s*\(")


def job_uses_checkout(job: dict) -> bool:
    for step in job.get("steps") or []:
        if isinstance(step, dict) and CHECKOUT in str(step.get("uses", "")):
            return True
    return False


def permission_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    """Jobs that declare a permissions block, check out code, and lack contents access.

    A job with NO permissions block inherits the workflow or repository default and is
    not this check's business -- only an explicit block triggers the deny-by-omission
    rule that makes the mistake possible.
    """
    out = []
    workflow_perms = workflow.get("permissions")
    for name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        perms = job.get("permissions", workflow_perms)
        if perms is None:
            continue
        if isinstance(perms, str):
            # Only the two documented shorthands grant contents; anything else
            # (notably `permissions: {}` written as a string, or a typo) does not.
            if perms in ("read-all", "write-all"):
                continue
            if job_uses_checkout(job):
                out.append(
                    f"{filename}: job `{name}` sets `permissions: {perms}`, which does "
                    f"not grant contents access, but runs {CHECKOUT}."
                )
            continue
        if not job_uses_checkout(job):
            continue
        if perms.get("contents") not in CONTENTS_OK:
            got = perms.get("contents", "not declared -> none")
            out.append(
                f"{filename}: job `{name}` runs {CHECKOUT} but its permissions block "
                f"gives contents = {got}. Declaring any scope sets the rest to `none`, "
                f"so checkout cannot clone a private repo and the job dies at step 1. "
                f"Add `contents: read`."
            )
    return out


def gate_ordering_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    """Steps carrying implicit `success()` after a `!cancelled()` step has appeared.

    Ordinal and name-blind on purpose: a setup step stranded after the gate boundary
    gets skipped by an earlier gate failure, and the gates after it then fail for a
    reason that has nothing to do with the code under test.

    A step counts as stranded when its `if:` invokes no status function -- which covers
    a step with no `if:` at all AND one with an ordinary condition like
    `runner.os == 'Linux'`, since GitHub implies `success() &&` in front of the latter.
    Both are skipped identically by an earlier failure.
    """
    out = []
    for name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        seen_gate = False
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            cond = str(step.get("if", ""))
            label = step.get("name") or step.get("uses", "<step>")
            if NO_CANCEL in cond:
                seen_gate = True
                continue
            if seen_gate and not STATUS_FN.search(cond):
                shown = f"`if: {cond}`" if cond else "no `if:`"
                out.append(
                    f"{filename}: job `{name}` step `{label}` has {shown}, so it carries "
                    f"an implicit `success()`, but runs AFTER a `{NO_CANCEL}` step. An "
                    f"earlier gate failure will skip it and the gates after it will then "
                    f"fail for the wrong reason. Move it above the first gate, or add a "
                    f"status function to its condition."
                )
    return out


def all_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    return permission_violations(workflow, filename) + gate_ordering_violations(workflow, filename)


def self_test() -> int:
    def wf(text):
        return yaml.safe_load(text)

    cases = [
        # (label, workflow, expected_violation_count)
        ("issues-write-only + checkout is rejected", wf("""
jobs:
  alarm:
    permissions: {issues: write}
    steps: [{uses: actions/checkout@v4}]
"""), 1),
        ("contents:read + issues:write is accepted", wf("""
jobs:
  alarm:
    permissions: {contents: read, issues: write}
    steps: [{uses: actions/checkout@v4}]
"""), 0),
        ("explicit contents:none + checkout is rejected", wf("""
jobs:
  alarm:
    permissions: {contents: none, issues: write}
    steps: [{uses: actions/checkout@v4}]
"""), 1),
        ("shorthand read-all is accepted", wf("""
jobs:
  alarm:
    permissions: read-all
    steps: [{uses: actions/checkout@v4}]
"""), 0),
        ("a non-granting shorthand is rejected", wf("""
jobs:
  alarm:
    permissions: none
    steps: [{uses: actions/checkout@v4}]
"""), 1),
        ("no permissions block is accepted (inherits default)", wf("""
jobs:
  plain:
    steps: [{uses: actions/checkout@v4}]
"""), 0),
        ("a job that never checks out is accepted", wf("""
jobs:
  writer:
    permissions: {issues: write}
    steps: [{run: echo hi}]
"""), 0),
        ("setup stranded after a gate is rejected", wf("""
jobs:
  operator:
    steps:
      - {name: Format, if: "${{ !cancelled() }}", run: fmt}
      - {name: Stage, run: stage}
      - {name: Check, if: "${{ !cancelled() }}", run: check}
"""), 1),
        ("setup before the first gate is accepted", wf("""
jobs:
  operator:
    steps:
      - {name: Stage, run: stage}
      - {name: Format, if: "${{ !cancelled() }}", run: fmt}
      - {name: Check, if: "${{ !cancelled() }}", run: check}
"""), 0),
        # A plain condition is implicitly `success() && ...`, so it is stranded too.
        # Matching only on "has no if:" would have closed the spelling, not the class.
        ("a NON-STATUS conditional after a gate is rejected", wf("""
jobs:
  operator:
    steps:
      - {name: Format, if: "${{ !cancelled() }}", run: fmt}
      - {name: Linux only, if: "runner.os == 'Linux'", run: x}
"""), 1),
        ("a status-function conditional after a gate is accepted", wf("""
jobs:
  operator:
    steps:
      - {name: Format, if: "${{ !cancelled() }}", run: fmt}
      - {name: Linux only, if: "${{ !cancelled() && runner.os == 'Linux' }}", run: x}
"""), 0),
        ("an explicit always() after a gate is accepted", wf("""
jobs:
  operator:
    steps:
      - {name: Format, if: "${{ !cancelled() }}", run: fmt}
      - {name: Report, if: "${{ always() }}", run: x}
"""), 0),
    ]
    failures = []
    for label, workflow, want in cases:
        got = len(all_violations(workflow))
        if got != want:
            failures.append(f"{label}: expected {want} violation(s), got {got}")
    if failures:
        print("check_workflows self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"check_workflows self-test: {len(cases)} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("paths", nargs="*", default=None)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    paths = args.paths or sorted(
        glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml")
    )
    if not paths:
        print("no workflows found to check", file=sys.stderr)
        return 1

    found, total_jobs = [], 0
    for path in paths:
        with open(path) as fh:
            workflow = yaml.safe_load(fh) or {}
        total_jobs += len(workflow.get("jobs") or {})
        found += all_violations(workflow, path)

    # A workflow that parses to zero jobs would otherwise pass vacuously.
    if total_jobs == 0:
        print(f"no jobs found across {len(paths)} workflow(s) — refusing to pass vacuously",
              file=sys.stderr)
        return 1

    if found:
        print("workflow checks FAILED:", file=sys.stderr)
        for v in found:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"workflow checks: {len(paths)} workflow(s), {total_jobs} job(s) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
