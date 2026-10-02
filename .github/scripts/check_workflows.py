#!/usr/bin/env python3
"""Workflow invariants that actionlint does not model.

Three checks. The first two were born from defects that shipped in this branch and were
caught by human review rather than by any gate; the third (cache saves) is described
after them:

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

3. CACHE SAVES COME FROM `main` ONLY (17tnw2b1f24). In a workflow that runs on pull
   requests, every `Swatinem/rust-cache` step must set `save-if` to the one canonical
   main-only expression. Without it each pull request saves a private copy of every
   job's cache (0.3-1.6 GB each); the repository's Actions cache limit (10 GB) is then
   exceeded, the least recently used entries are evicted -- main's included -- and main's
   own jobs start cold (a cold Windows operator-native job runs about 35 minutes against
   about 4 warm). The cache key has no ref in it, so a pull request restores main's entry
   exactly; it does not need to save its own.

   THE COST OF THIS RULE, written here so the failure message is not read as arbitrary: a
   pull request can only restore what main holds. While main has no entry for a job (the
   job is red on main -- a red job saves nothing --, the entry was evicted, or a lockfile
   or toolchain change moved the key), every push of every pull request runs that job
   cold, where before a PR's first push seeded an entry its later pushes reused. The remedy
   is to keep main's entries whole (ClickUp 17tnw2b1waw), not to let pull requests save.

   `subosito/flutter-action` is covered too, differently: it has no `save-if`, so the rule
   is that neither `cache:` nor `pub-cache:` is switched on. Its SDK entry is 1.72 GB (the
   pub entry 39 MB), the largest single entry in the repo: about 17.6% of a 10 GB limit,
   and the first entry evicted at the limit (Inferred; mobile runs are rarer). The reason
   is BYTES, not time -- what the cache saves in time is roughly a wash.

   The rule is deliberately NOT "every rust-cache step in every workflow": a
   `workflow_dispatch`-only workflow (windows-installer.yml) cannot run on a pull
   request, is normally dispatched from a feature branch, and would be cold on every
   dispatch if only main could save. Only the pull-request-reachable class is checked.
   Exactly ONE spelling is accepted (`github.ref == 'refs/heads/main'`), so an inverted,
   always-true or literal value cannot pass for a decision. `github.ref_name == 'main'`
   is refused on purpose: it is also true for a tag named `main`.

Known gaps, so the boundary is written down rather than assumed:
   - Check 3 covers `Swatinem/rust-cache` and `subosito/flutter-action` only. Other steps
     that save to the Actions cache (setup-node / setup-python `cache:`, a bare
     `actions/cache`) are not checked: the first two expose no `save-if` input (read from
     their action.yml at the versions ci.yml pins) and their entries are about 26 MB each
     per pull request, so there is no one-line fix worth enforcing. See ClickUp
     17tnw2b1f24.
   - Check 3 treats `pull_request` and `pull_request_target` as the pull-request triggers
     (both are pinned by self-test cases). For `pull_request_target` -- and `workflow_run`
     and `issue_comment` -- GitHub sets `github.ref` to the DEFAULT branch, so the
     canonical `save-if` is TRUE on every such run: the check accepts it and it protects
     nothing there. `workflow_run`, `issue_comment`, `merge_group` and `pull_request_review`
     are not treated as PR triggers at all, and an unfiltered `push:` trigger (which would
     save from feature branches) is not detected. None of these exists in this repo today
     (verified when written); ci.yml pushes on `main` only. Not hardened here.
   - Check 3 reads the `steps:` of the file it is given. A `rust-cache` step inside a
     reusable workflow (`on: workflow_call`, exempt because it has no PR trigger of its
     own), a PR-triggered job that CALLS one (`jobs.<id>.uses:` has no steps), a local
     composite action, or a renamed fork of the action is invisible. None exist
     (verified when written: no `.github/actions/`, no `workflow_call`). Resolving them is
     deliberately not attempted.
   - The expression match is strict, so a legitimate narrower form (`... && matrix.os ==
     ...`, a parenthesised copy of the canonical one) is rejected; the message names the
     canonical form to use.
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
# Check 3. GitHub action names are case-insensitive, so the comparison is on lower().
RUST_CACHE = "swatinem/rust-cache"
FLUTTER_ACTION = "subosito/flutter-action"
PR_TRIGGERS = {"pull_request", "pull_request_target"}
SAVE_IF_MAIN = "${{ github.ref == 'refs/heads/main' }}"
# Exactly ONE main-only spelling, whole-value. A substring test would accept
# `github.ref != 'refs/heads/main'` (inverted) and `true || github.ref == ...`. The
# `github.ref_name == 'main'` form is NOT accepted: it is also true for a tag named main.
MAIN_ONLY = re.compile(r"^\$\{\{\s*github\.ref\s*==\s*'refs/heads/main'\s*\}\}$")


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


def workflow_triggers(workflow: dict) -> set[str]:
    """The event names a workflow runs on, whichever of the three `on:` shapes it uses.

    PyYAML is a YAML 1.1 parser, so the bare key `on` loads as the boolean True, not the
    string "on". Both are looked up; missing the first would make every workflow look
    trigger-less and the check below silently pass everything.
    """
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, (list, dict)):
        return {str(event) for event in on}
    return set()


def cache_save_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    """Cache-saving steps, in a pull-request-triggered workflow, that can save from a
    pull request: `Swatinem/rust-cache` without the main-only `save-if`, and
    `subosito/flutter-action` with its built-in `cache:` switched on.

    For rust-cache only the canonical main-only `save-if` passes; a missing `with:`, a
    missing `save-if`, a literal `true`, or an inverted expression is a violation. For
    flutter-action the action has no `save-if`, so any `cache` or `pub-cache` other than
    absent or literal false is a violation (`pub-cache: true` re-enables the pub-cache
    save even with `cache` off). A workflow with no pull-request trigger is exempt (see
    the module docstring for why).
    """
    if not (workflow_triggers(workflow) & PR_TRIGGERS):
        return []
    out = []
    for name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            action = str(step.get("uses", "")).split("@")[0].lower()
            if action == FLUTTER_ACTION:
                inputs = step.get("with") or {}
                for key in ("cache", "pub-cache"):
                    value = str(inputs.get(key, "")).strip().lower()
                    if value in ("", "false"):
                        continue
                    label = step.get("name") or step.get("uses", "<step>")
                    out.append(
                        f"{filename}: job `{name}` step `{label}` sets `{key}: {value}` on "
                        f"subosito/flutter-action in a workflow that runs on pull requests. "
                        f"The action has no `save-if`, so every pull request would save its "
                        f"own Flutter SDK copy (1.72 GB) and pub cache (39 MB): about 17.6% "
                        f"of a 10 GB Actions cache limit, for a time saving that is roughly "
                        f"a wash (17tnw2b1f24). Remove `cache:` and `pub-cache:`."
                    )
                continue
            if action != RUST_CACHE:
                continue
            value = str((step.get("with") or {}).get("save-if", "")).strip()
            if MAIN_ONLY.match(value):
                continue
            label = step.get("name") or step.get("uses", "<step>")
            shown = f"`{value}`" if value else "not set (the default is to save)"
            out.append(
                f"{filename}: job `{name}` step `{label}` runs Swatinem/rust-cache in a "
                f"workflow that runs on pull requests, but its `save-if` is {shown}. A pull "
                f"request that saves writes its own private copy of the cache, which pushes "
                f"the repo over its Actions cache limit (10 GB) and gets main's entries "
                f"evicted (17tnw2b1f24). Set `save-if: {SAVE_IF_MAIN}` (that exact "
                f"spelling) so pull requests only restore."
            )
    return out


def all_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    return (
        permission_violations(workflow, filename)
        + gate_ordering_violations(workflow, filename)
        + cache_save_violations(workflow, filename)
    )


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
        # Check 3: rust-cache saves come from main only (17tnw2b1f24). `on:` is written the
        # way the real files write it, so these also prove the YAML-1.1 `on` -> True quirk
        # in workflow_triggers() is handled; a loader that missed it would pass them all.
        ("rust-cache with no save-if on a PR-triggered workflow is rejected", wf("""
on: {push: {branches: [main]}, pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {workspaces: implementation/desktop}
"""), 1),
        ("rust-cache with the canonical main-only save-if is accepted", wf("""
on: {push: {branches: [main]}, pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: implementation/desktop
          save-if: ${{ github.ref == 'refs/heads/main' }}
"""), 0),
        # Refused on purpose, not an oversight: `github.ref_name == 'main'` is also true for a
        # tag named `main`, so exactly one spelling is allowed.
        ("the github.ref_name == 'main' spelling is rejected (a tag can be named main)", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with:
          save-if: ${{ github.ref_name == 'main' }}
"""), 1),
        # Pins `pull_request_target` as a pull-request trigger. No other case uses it, so
        # dropping it from PR_TRIGGERS used to pass every case (Cody and Quinn, PR #148).
        # NOTE: this only pins the DETECTION. On pull_request_target `github.ref` is the
        # default branch, so the canonical save-if is not protective there; see the module
        # docstring's Known gaps.
        ("a pull_request_target-only workflow is a PR trigger: missing save-if is rejected", wf("""
on: {pull_request_target: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {workspaces: x}
"""), 1),
        ("a literal save-if: true is rejected", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {save-if: true}
"""), 1),
        ("an always-true expression is rejected", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with:
          save-if: ${{ true || github.ref == 'refs/heads/main' }}
"""), 1),
        # The inverted form is the mistake most likely to be typed by hand, and it saves
        # on every PR while NOT saving on main -- the exact opposite of the intent.
        ("an inverted save-if is rejected", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
        with:
          save-if: ${{ github.ref != 'refs/heads/main' }}
"""), 1),
        ("rust-cache with no `with:` block at all is rejected", wf("""
on: [push, pull_request]
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
"""), 1),
        ("the string form `on: pull_request` is detected", wf("""
on: pull_request
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@v2
"""), 1),
        ("an action-name case difference does not hide the step", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: swatinem/rust-cache@v2
"""), 1),
        ("a SHA-pinned rust-cache with the canonical save-if is accepted", wf("""
on: {pull_request: {}}
jobs:
  rust:
    steps:
      - uses: Swatinem/rust-cache@0123456789abcdef0123456789abcdef01234567
        with:
          save-if: ${{ github.ref == 'refs/heads/main' }}
"""), 0),
        ("two steps, one missing save-if: exactly one violation", wf("""
on: {pull_request: {}}
jobs:
  a:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {save-if: "${{ github.ref == 'refs/heads/main' }}"}
  b:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {workspaces: x}
"""), 1),
        # Deliberate exemption, pinned so it cannot be widened or dropped by accident: a
        # dispatch-only workflow can never run on a PR and is normally run from a branch.
        ("rust-cache in a workflow with no PR trigger is exempt", wf("""
on: {workflow_dispatch: {}}
jobs:
  build:
    steps:
      - uses: Swatinem/rust-cache@v2
        with: {workspaces: implementation/desktop}
"""), 0),
        ("a bare actions/cache step is out of scope here (a documented gap)", wf("""
on: {pull_request: {}}
jobs:
  other:
    steps:
      - uses: actions/cache@v5
        with: {path: x, key: y}
"""), 0),
        # flutter-action has no save-if, so the only safe setting is no cache at all.
        ("flutter-action with cache: true on a PR-triggered workflow is rejected", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {channel: stable, cache: true}
"""), 1),
        ("flutter-action with a cache expression is rejected too", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with:
          cache: ${{ github.ref == 'refs/heads/main' }}
"""), 1),
        ("flutter-action with no cache input is accepted", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {channel: stable}
"""), 0),
        ("flutter-action with cache: false is accepted", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {channel: stable, cache: false}
"""), 0),
        # `pub-cache: true` re-enables the pub-cache save even with `cache` off (the action
        # runs its pub step when `pub-cache == 'true'`), so it must be refused as well.
        ("flutter-action with pub-cache: true (cache off) is rejected", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {channel: stable, pub-cache: true}
"""), 1),
        ("flutter-action with cache: true AND pub-cache: true reports both", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {cache: true, pub-cache: true}
"""), 2),
        ("flutter-action with pub-cache: false is accepted", wf("""
on: {pull_request: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {channel: stable, pub-cache: false}
"""), 0),
        ("flutter-action cache: true in a dispatch-only workflow is exempt", wf("""
on: {workflow_dispatch: {}}
jobs:
  flutter:
    steps:
      - uses: subosito/flutter-action@v2
        with: {cache: true}
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
