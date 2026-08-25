#!/usr/bin/env python3
"""Refuse a workflow job that checks out code without the token scope to do it.

WHY THIS EXISTS
Declaring ANY `permissions:` block on a job sets every scope NOT listed to `none`.
So a job written as:

    permissions:
      issues: write
    steps:
      - uses: actions/checkout@v4

gets `contents: none`, and on a private repository checkout cannot clone. The first
step fails and every step after it -- including whatever the job existed to do --
never runs.

That is not hypothetical here: the `ci-alarm` job shipped exactly that shape in
review. It would have been a permanently dead alarm sitting next to a CLAUDE.md
telling readers the ci-red issue is "the only alarm" and to trust it. Security
review caught it by eye.

`actionlint` does NOT catch this (verified), so nothing else in the pipeline would
have. Hence a purpose-built check: cheap, exact, and it fails closed.

Self-test: `check_workflow_permissions.py --self-test`
"""

from __future__ import annotations

import argparse
import glob
import sys

import yaml

CHECKOUT = "actions/checkout"
# Scopes that let the token clone the repo.
CONTENTS_OK = {"read", "write"}


def job_uses_checkout(job: dict) -> bool:
    for step in job.get("steps") or []:
        if isinstance(step, dict) and CHECKOUT in str(step.get("uses", "")):
            return True
    return False


def violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
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
        # No explicit block anywhere: repository default applies, nothing to check.
        if perms is None:
            continue
        # The shorthand forms grant or revoke everything at once.
        if isinstance(perms, str):
            if perms == "read-all" or perms == "write-all":
                continue
            out.append(f"{filename}: job `{name}` sets `permissions: {perms}`")
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


def self_test() -> int:
    bad = yaml.safe_load("""
jobs:
  alarm:
    permissions:
      issues: write
    steps:
      - uses: actions/checkout@v4
""")
    good = yaml.safe_load("""
jobs:
  alarm:
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4
""")
    no_block = yaml.safe_load("""
jobs:
  plain:
    steps:
      - uses: actions/checkout@v4
""")
    no_checkout = yaml.safe_load("""
jobs:
  writer:
    permissions:
      issues: write
    steps:
      - run: echo hi
""")
    failures = []
    if len(violations(bad)) != 1:
        failures.append("the issues-write-only job with checkout must be REJECTED")
    if violations(good):
        failures.append("contents:read + issues:write must be ACCEPTED")
    if violations(no_block):
        failures.append("a job with no permissions block must be ACCEPTED (inherits default)")
    if violations(no_checkout):
        failures.append("a job that never checks out must be ACCEPTED")
    if failures:
        print("check_workflow_permissions self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("check_workflow_permissions self-test: all cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("paths", nargs="*", default=None)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    paths = args.paths or sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
    if not paths:
        print("no workflows found to check", file=sys.stderr)
        return 1

    found = []
    for path in paths:
        with open(path) as fh:
            found += violations(yaml.safe_load(fh) or {}, path)

    if found:
        print("workflow permissions check FAILED:", file=sys.stderr)
        for v in found:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"workflow permissions check: {len(paths)} workflow(s) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
