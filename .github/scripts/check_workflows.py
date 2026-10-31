#!/usr/bin/env python3
"""Workflow invariants that actionlint does not model.

Four checks. The first two were born from defects that shipped in this branch and were
caught by human review rather than by any gate; the third (cache saves) and the fourth
(protected environments) are described after them:

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
   request, historically allowed feature-branch dispatches. Installer workflows now reject
   non-main dispatches (17tnw2bbhxf), but the cache rule remains PR-scoped. Only the
   pull-request-reachable class is checked.
   Exactly ONE spelling is accepted (`github.ref == 'refs/heads/main'`), so an inverted,
   always-true or literal value cannot pass for a decision. `github.ref_name == 'main'`
   is refused on purpose: it is also true for a tag named `main`.

4. SECRETS AND PROTECTED ENVIRONMENTS (17tnw2b2jqd). The translations publish workflow
   holds the Space's access key behind an environment with a named approver. What follows
   is EXACTLY what this check enforces, and then what it does not.

   ENFORCED IN EVERY WORKFLOW (secrets):
   a. A secret other than GITHUB_TOKEN, in ANY spelling inside an expression
      (`secrets.NAME`, `secrets["NAME"]`, `secrets['NAME']`, `toJSON(secrets)`, a bare
      `secrets`, `secrets[format(...)]`), may appear ONLY in the `env:` of a step of a job
      that declares `environment:`, and only in a step whose `run:` calls
      `scripts/publish_translations.py upload`. So: not at workflow level, not in a
      job-level `env:` (every step would read it), not in a job without an environment
      (it would run without the approval, and on a repository secret), not in `with:`
      (handed to an action), not in `if:`, not spliced into `run:` text (injection and log
      exposure), not in a step that is not an upload step, and no job-level `secrets:`
      (`inherit`). The word inside prose or inside `needs.x.outputs.secrets` is not a
      reference and is ignored.

   ENFORCED IN A WORKFLOW THAT HAS A JOB WITH `environment:`:
   b. Triggered by `workflow_dispatch` ONLY (a push, pull_request, schedule or
      workflow_run trigger would let something other than a person who chose to run it
      reach the job).
   c. Workflow `permissions:` is exactly `contents: read`, and no job declares anything
      wider.
   d. The dispatch inputs declare `dry_run`, a boolean whose default is true (a dry run is
      what you get unless you ask otherwise).
   e. Every environment job: names an environment in PROTECTED_ENVIRONMENTS; has exactly
      `if: ${{ !inputs.dry_run }}` (the one spelling, as with check 3); has a concurrency
      group whose `cancel-in-progress` is literally false (job- or workflow-level), so a
      second publish waits and an upload is never cut half way; and its FIRST step's `run:`
      mentions `refs/heads/main` (the main-only guard).
   f. Every job in the file runs on `ubuntu-*` (a string, not a matrix or a list), has no
      job-level `uses:`, and every step `uses:` an `actions/*` action pinned by a full
      40-character commit SHA (no tag, no branch, no third-party action, no local or
      docker action).

   HELD ONLY BY REVIEW (this check cannot see them):
   - That there are exactly two upload steps, and what the scripts do with the key:
     `publish_translations.py` is reviewed by people; this check only fixes WHICH step may
     hold it.
   - That the main-only guard actually refuses: only that the first step mentions
     `refs/heads/main`. The same for the semantics of the `if:` beyond its spelling.
   - Anything on GitHub rather than in the file: that PROTECTED_ENVIRONMENTS names a real
     environment with a required reviewer and a `main`-only branch policy, that the
     secrets are environment secrets and not repository secrets, that `main` itself is
     protected (it is not today), and the fork-PR approval policy.
   - A secret handed to a reusable workflow, an environment chosen by an expression, and
     reads that go through a file rather than a `${{ }}` expression.
   - A workflow with no `environment:` job is held only to (a); b to f do not apply to it.

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


# Check 4. See the docstring for exactly what is and is not enforced.
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
# The `secrets` context however it is spelled. The look-behind keeps `needs.x.outputs.secrets` and `foo_secrets` out.
SECRETS_CONTEXT = re.compile(r"(?<![\w.$-])secrets\b", re.I)
GITHUB_TOKEN_AFTER = re.compile(r"\s*(?:\.\s*GITHUB_TOKEN\b|\[\s*(['\"])GITHUB_TOKEN\1\s*\])", re.I)
UPLOAD_STEP_RUN = re.compile(r"scripts/publish_translations\.py\s+upload\b")
DISPATCH_ONLY = {"workflow_dispatch"}
# Environments that really exist on GitHub with a required reviewer and a main-only branch policy. Held by review.
PROTECTED_ENVIRONMENTS = {"translations-publish"}
PINNED_ACTION = re.compile(r"^actions/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._/-]+)?@[0-9a-f]{40}$")
DRY_RUN_IF = re.compile(r"^\$\{\{\s*!\s*inputs\.dry_run\s*\}\}$")


def secret_refs(value, bare: bool = False) -> list[str]:
    """Every reference to a secret (other than GITHUB_TOKEN) inside `value`, as short excerpts.

    Only text inside `${{ }}` counts, except when `bare` (an `if:`, which GitHub evaluates as an expression without
    the wrapper). Keys are scanned too. Any spelling counts: `secrets.X`, `secrets["X"]`, `toJSON(secrets)`, bare."""
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in value.items():
            out += secret_refs(k) + secret_refs(v, bare)
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out += secret_refs(v, bare)
        return out
    if value is None or isinstance(value, bool):
        return []
    text = str(value)
    expressions = [text] if bare and "${{" not in text else EXPRESSION.findall(text)
    found = []
    for expr in expressions:
        for m in SECRETS_CONTEXT.finditer(expr):
            if GITHUB_TOKEN_AFTER.match(expr, m.end()):
                continue
            found.append(expr[m.start():m.start() + 40].strip())
    return found


def secret_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    """Check 4a, in every workflow: where a secret may be referenced."""
    out = []
    top = {k: v for k, v in workflow.items() if k != "jobs"}
    for ref in sorted(set(secret_refs(top))):
        out.append(f"{filename}: `{ref}` is referenced at the workflow level, so every job and step could read it. A "
                   f"secret belongs in the `env:` of the one upload step of an environment job.")
    for jname, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        if "secrets" in job:
            out.append(f"{filename}: job `{jname}` passes secrets on with a job-level `secrets:` (for example `inherit`). "
                       f"Not allowed: the key may only reach an upload step of an environment job.")
        if "environment" not in job:
            for ref in sorted(set(secret_refs(job))):
                out.append(f"{filename}: job `{jname}` references `{ref}` but declares no `environment:`, so it would run "
                           f"without an approval and against repository-level secrets.")
            continue
        job_level = {k: v for k, v in job.items() if k not in ("steps", "if")}
        for ref in sorted(set(secret_refs(job_level) + secret_refs(job.get("if"), bare=True))):
            out.append(f"{filename}: job `{jname}` references `{ref}` outside a step's `env:` (job-level env, `if:`, "
                       f"`concurrency:` or another job key), so more than one step could read it.")
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            label = step.get("name") or step.get("uses") or "<step>"
            is_upload = bool(UPLOAD_STEP_RUN.search(str(step.get("run", ""))))
            for key, val in step.items():
                refs = sorted(set(secret_refs(val, bare=(key == "if"))))
                if not refs or (key == "env" and is_upload):
                    continue
                where = ("the `env:` of a step that does not call `publish_translations.py upload`" if key == "env"
                         else f"`{key}:`")
                for ref in refs:
                    out.append(f"{filename}: job `{jname}` step `{label}` uses `{ref}` in {where}. A secret may only be "
                               f"passed through the `env:` of a step whose `run:` calls `publish_translations.py upload` "
                               f"(not handed to an action, spliced into a script or a condition, or given to another step).")
    return out


def _environment_name(job: dict):
    env = job.get("environment")
    if isinstance(env, dict):
        env = env.get("name")
    return env if isinstance(env, str) else None


def _concurrency_never_cancels(conc) -> bool:
    if isinstance(conc, str):  # a bare group name: cancel-in-progress defaults to false
        return bool(conc.strip())
    if isinstance(conc, dict):
        cancel = conc.get("cancel-in-progress", False)
        return bool(str(conc.get("group", "")).strip()) and (cancel is False or str(cancel).strip().lower() == "false")
    return False


def protected_environment_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    """Check 4b to 4f, in a workflow that has a job with `environment:`. Others are not this check's business."""
    jobs = {n: j for n, j in (workflow.get("jobs") or {}).items() if isinstance(j, dict)}
    env_jobs = {n: j for n, j in jobs.items() if "environment" in j}
    if not env_jobs:
        return []
    out = []
    extra = workflow_triggers(workflow) - DISPATCH_ONLY
    if extra:
        out.append(f"{filename}: a workflow with an `environment:` job must be triggered by workflow_dispatch only, but it "
                   f"also runs on {sorted(extra)}. Its secrets sit behind a named approver; another trigger bypasses the point.")
    if workflow.get("permissions") != {"contents": "read"}:
        out.append(f"{filename}: the workflow `permissions:` must be exactly `contents: read` (got "
                   f"{workflow.get('permissions')!r}).")
    for jname, job in jobs.items():
        if "permissions" in job and job["permissions"] != {"contents": "read"}:
            out.append(f"{filename}: job `{jname}` declares `permissions: {job['permissions']!r}`; only `contents: read` is allowed.")
    on = workflow.get("on", workflow.get(True))
    dispatch = on.get("workflow_dispatch") if isinstance(on, dict) else None
    inputs = dispatch.get("inputs") if isinstance(dispatch, dict) else None
    dry = inputs.get("dry_run") if isinstance(inputs, dict) else None
    if not (isinstance(dry, dict) and dry.get("type") == "boolean" and dry.get("default") is True):
        out.append(f"{filename}: the dispatch inputs must declare `dry_run` as a boolean whose default is true (a dry run is "
                   f"what you get unless you ask otherwise); got {dry!r}.")
    for jname, job in env_jobs.items():
        name = _environment_name(job)
        if name not in PROTECTED_ENVIRONMENTS:
            out.append(f"{filename}: job `{jname}` uses environment {name!r}, which is not a known protected environment "
                       f"({sorted(PROTECTED_ENVIRONMENTS)}).")
        if not DRY_RUN_IF.match(str(job.get("if", "")).strip()):
            out.append(f"{filename}: job `{jname}` must have exactly `if: ${{{{ !inputs.dry_run }}}}` (got {job.get('if')!r}), so "
                       f"it runs only when a real publish was asked for.")
        if not _concurrency_never_cancels(job.get("concurrency", workflow.get("concurrency"))):
            out.append(f"{filename}: job `{jname}` needs a `concurrency:` group with `cancel-in-progress: false`, so two "
                       f"publishes never run at once and an upload is never cut half way.")
        steps = job.get("steps") or []
        first = steps[0] if steps and isinstance(steps[0], dict) else {}
        if "refs/heads/main" not in str(first.get("run", "")):
            out.append(f"{filename}: the first step of job `{jname}` must be the main-only guard (its `run:` mentions "
                       f"`refs/heads/main`).")
    for jname, job in jobs.items():
        runs_on = job.get("runs-on")
        if not (isinstance(runs_on, str) and runs_on.startswith("ubuntu-")):
            out.append(f"{filename}: job `{jname}` must run on an `ubuntu-*` runner given as one string (got {runs_on!r}).")
        if "uses" in job:
            out.append(f"{filename}: job `{jname}` calls a reusable workflow (`uses:`); not allowed here.")
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("uses") is not None and not PINNED_ACTION.match(str(step["uses"])):
                out.append(f"{filename}: job `{jname}` uses `{step['uses']}`; in this workflow every action must be an "
                           f"`actions/*` action pinned by a full 40-character commit SHA.")
    return out


# Installer packaging is owner-triggered, main-only work (17tnw2bbhxf). Keep this
# check inside the existing always-run workflow gate: it adds no paid runner.
INSTALLER_GUARD = "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}"


def installer_violations(workflow: dict, filename: str) -> list[str]:
    if not filename.endswith(("-installer.yml", "-installer.yaml")):
        return []
    out = []
    if not workflow.get("jobs"):
        out.append(f"{filename}: installer workflow requires a guarded packaging job")
    triggers = workflow.get("on", workflow.get(True, {}))
    if not isinstance(triggers, dict) or set(triggers) != {"workflow_dispatch"}:
        out.append(f"{filename}: installer packaging must use workflow_dispatch only")
    for name, job in (workflow.get("jobs") or {}).items():
        if job.get("if") != INSTALLER_GUARD:
            out.append(f"{filename}: installer job {name} requires the exact manual/main-only job guard")
        checkouts = [step for step in job.get("steps", [])
                     if str(step.get("uses", "")).startswith("actions/checkout@")]
        if len(checkouts) != 1 or checkouts[0].get("with", {}).get("ref") != "${{ github.sha }}":
            out.append(f"{filename}: installer job {name} must checkout the immutable dispatch SHA")
    return out


def installer_cases() -> list[tuple[str, dict, str | None]]:
    def example():
        return yaml.safe_load("""
on: {workflow_dispatch: {}}
jobs:
  build:
    if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}
    steps:
      - uses: actions/checkout@v7
        with: {ref: '${{ github.sha }}'}
""")
    cases = [("manual-main pinned checkout accepted", example(), None)]
    empty = example()
    empty["jobs"] = {}
    cases.append(("installer without jobs rejected", empty, "guarded packaging job"))
    for event in ("push", "pull_request", "release", "schedule", "workflow_run", "workflow_call"):
        w = example()
        w[True][event] = {}
        cases.append((f"installer automatic {event} rejected", w, "workflow_dispatch only"))
    for guard in (None, "${{ github.ref == 'refs/heads/main' }}",
                  "${{ github.event_name == 'workflow_dispatch' }}",
                  "${{ github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main' }}",
                  "${{ github.event_name == 'workflow_dispatch' && github.ref_name == 'main' }}"):
        w = example()
        w["jobs"]["build"]["if"] = guard
        cases.append((f"installer broad guard rejected: {guard}", w, "manual/main-only"))
    for ref in (None, "main", "${{ github.ref }}", "${{ inputs.ref }}"):
        w = example()
        w["jobs"]["build"]["steps"][0]["with"]["ref"] = ref
        cases.append((f"installer mutable checkout rejected: {ref}", w, "immutable dispatch SHA"))
    return cases


def all_violations(workflow: dict, filename: str = "<workflow>") -> list[str]:
    return (
        permission_violations(workflow, filename)
        + gate_ordering_violations(workflow, filename)
        + cache_save_violations(workflow, filename)
        + secret_violations(workflow, filename)
        + protected_environment_violations(workflow, filename)
        + installer_violations(workflow, filename)
    )


GOOD_PUBLISH = """
on:
  workflow_dispatch:
    inputs:
      only: {required: true, default: BSB, type: string}
      dry_run: {required: true, default: true, type: boolean}
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: python3 scripts/publish_translations.py plan
  publish:
    needs: build
    if: ${{ !inputs.dry_run }}
    runs-on: ubuntu-latest
    environment: translations-publish
    concurrency:
      group: publish-translations
      cancel-in-progress: false
    steps:
      - name: Publish from main only
        run: |
          if [ "$GITHUB_REF" != "refs/heads/main" ]; then exit 1; fi
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - name: Upload
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.SPACES_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.SPACES_SECRET_ACCESS_KEY }}
        run: python3 scripts/publish_translations.py upload --stage assets
"""
SHA_A = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def check4_cases():
    """(label, workflow, needle). needle None: no violation at all; else some violation must mention it.

    Each case starts from GOOD_PUBLISH, which must pass every check, and breaks ONE thing."""

    def good():
        return yaml.safe_load(GOOD_PUBLISH)

    def mutated(fn):
        w = good()
        fn(w)
        return w

    def job(w, name):
        return w["jobs"][name]

    def upload(w):
        return job(w, "publish")["steps"][2]

    def on(w):
        return w["on"] if "on" in w else w[True]

    cases = [
        ("the real shape passes every check", good(), None),
        ("GITHUB_TOKEN is not a protected secret, in any spelling, in any job", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"A": "${{ secrets.GITHUB_TOKEN }}", "B": "${{ secrets['GITHUB_TOKEN'] }}",
                                                             "C": '${{ secrets["github_token"] }}'})), None),
        ("secrets.GITHUB_TOKEN_X is not GITHUB_TOKEN", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"A": "${{ secrets.GITHUB_TOKEN_X }}"})), "no `environment:`"),
        ("prose that says 'secrets' is not a reference", mutated(
            lambda w: job(w, "build")["steps"][1].update(run='echo "no secrets are used here"')), None),
        ("needs.x.outputs.secrets is not the secrets context", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"A": "${{ needs.x.outputs.secrets }}"})), None),
        # --- b: triggers ---
        ("a push trigger is rejected", mutated(lambda w: on(w).update(push={"branches": ["main"]})), "workflow_dispatch only"),
        ("a pull_request trigger is rejected", mutated(lambda w: on(w).update(pull_request={})), "workflow_dispatch only"),
        ("a schedule trigger is rejected", mutated(lambda w: on(w).update(schedule=[{"cron": "0 0 * * *"}])), "workflow_dispatch only"),
        ("a workflow_run trigger is rejected", mutated(lambda w: on(w).update(workflow_run={"workflows": ["ci"]})), "workflow_dispatch only"),
        ("a workflow_call trigger is rejected", mutated(lambda w: on(w).update(workflow_call={})), "workflow_dispatch only"),
        # --- a: where a secret may be ---
        ("a secret in the workflow-level env is rejected", mutated(
            lambda w: w.update(env={"K": "${{ secrets.SPACES_ACCESS_KEY_ID }}"})), "workflow level"),
        ("a secret in a job-level env is rejected", mutated(
            lambda w: job(w, "publish").update(env={"K": "${{ secrets.SPACES_ACCESS_KEY_ID }}"})), "outside a step's `env:`"),
        ("a secret in a step of a job with no environment is rejected", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"K": "${{ secrets.SPACES_ACCESS_KEY_ID }}"})), "no `environment:`"),
        ("removing the environment from the publish job is rejected (its secret has nowhere to be)", mutated(
            lambda w: job(w, "publish").pop("environment")), "no `environment:`"),
        ("a secret in another step's env of the environment job is rejected", mutated(
            lambda w: job(w, "publish")["steps"][1].update(env={"K": "${{ secrets.SPACES_ACCESS_KEY_ID }}"})), "does not call"),
        ("a secret in the env of an upload-looking step that calls something else is rejected", mutated(
            lambda w: upload(w).update(run="echo hello")), "does not call"),
        ("a secret spliced into run text is rejected", mutated(
            lambda w: upload(w).update(run="python3 scripts/publish_translations.py upload --key ${{ secrets.SPACES_ACCESS_KEY_ID }}")),
         "`run:`"),
        ("a secret handed to an action through with: is rejected", mutated(
            lambda w: job(w, "publish")["steps"][1].update(**{"with": {"token": "${{ secrets.SPACES_ACCESS_KEY_ID }}"}})), "`with:`"),
        ("a secret in a step condition (wrapped) is rejected", mutated(
            lambda w: upload(w).update(**{"if": "${{ secrets.SPACES_ACCESS_KEY_ID != '' }}"})), "`if:`"),
        ("a secret in a step condition (bare) is rejected", mutated(
            lambda w: upload(w).update(**{"if": "secrets.SPACES_ACCESS_KEY_ID != ''"})), "`if:`"),
        ("a secret in the job condition is rejected", mutated(
            lambda w: job(w, "publish").update(**{"if": "${{ !inputs.dry_run && secrets.X != '' }}"})), "outside a step's `env:`"),
        ("the secrets[\"NAME\"] spelling at workflow level is rejected", mutated(
            lambda w: w.update(env={"K": '${{ secrets["SPACES_ACCESS_KEY_ID"] }}'})), "workflow level"),
        ("the secrets['NAME'] spelling in a job env is rejected", mutated(
            lambda w: job(w, "publish").update(env={"K": "${{ secrets['SPACES_ACCESS_KEY_ID'] }}"})), "outside a step's `env:`"),
        ("toJSON(secrets) at workflow level is rejected", mutated(lambda w: w.update(env={"K": "${{ toJSON(secrets) }}"})), "workflow level"),
        ("toJSON(secrets) in a step of a job with no environment is rejected", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"K": "${{ toJSON(secrets) }}"})), "no `environment:`"),
        ("a bare ${{ secrets }} is rejected", mutated(lambda w: w.update(env={"K": "${{ secrets }}"})), "workflow level"),
        ("secrets[format(...)] is rejected", mutated(
            lambda w: job(w, "build")["steps"][1].update(env={"K": "${{ secrets[format('{0}', 'X')] }}"})), "no `environment:`"),
        ("a secret in the step env of a step with a spelled-differently reference is still only allowed in an upload step", mutated(
            lambda w: job(w, "publish")["steps"][1].update(env={"K": "${{ secrets['SPACES_ACCESS_KEY_ID'] }}"})), "does not call"),
        ("a job-level `secrets: inherit` is rejected", mutated(lambda w: job(w, "build").update(secrets="inherit")), "job-level `secrets:`"),
        # --- c: permissions ---
        ("workflow permissions contents: write is rejected", mutated(lambda w: w.update(permissions={"contents": "write"})), "exactly `contents: read`"),
        ("a missing workflow permissions block is rejected", mutated(lambda w: w.pop("permissions")), "exactly `contents: read`"),
        ("an extra permission is rejected", mutated(lambda w: w.update(permissions={"contents": "read", "id-token": "write"})),
         "exactly `contents: read`"),
        ("a wider job permission is rejected", mutated(lambda w: job(w, "publish").update(permissions={"contents": "write"})), "only `contents: read`"),
        # --- d: dry run ---
        ("a dry_run default of false is rejected", mutated(lambda w: on(w)["workflow_dispatch"]["inputs"]["dry_run"].update(default=False)),
         "dry_run"),
        ("a missing dry_run input is rejected", mutated(lambda w: on(w)["workflow_dispatch"]["inputs"].pop("dry_run")), "dry_run"),
        ("a dry_run input that is a string is rejected", mutated(
            lambda w: on(w)["workflow_dispatch"]["inputs"]["dry_run"].update(type="string")), "dry_run"),
        ("a dry_run input with no default is rejected", mutated(lambda w: on(w)["workflow_dispatch"]["inputs"]["dry_run"].pop("default")), "dry_run"),
        ("a dry_run default of the string 'true' is rejected", mutated(
            lambda w: on(w)["workflow_dispatch"]["inputs"]["dry_run"].update(default="true")), "dry_run"),
        # --- e: the environment job ---
        ("an environment that is not a known protected one is rejected", mutated(lambda w: job(w, "publish").update(environment="staging")),
         "not a known protected environment"),
        ("an environment given as a mapping with another name is rejected", mutated(
            lambda w: job(w, "publish").update(environment={"name": "staging"})), "not a known protected environment"),
        ("an environment given as a mapping with the right name is accepted", mutated(
            lambda w: job(w, "publish").update(environment={"name": "translations-publish"})), None),
        ("a publish job with no if is rejected", mutated(lambda w: job(w, "publish").pop("if")), "inputs.dry_run"),
        ("an inverted if is rejected", mutated(lambda w: job(w, "publish").update(**{"if": "${{ inputs.dry_run }}"})), "inputs.dry_run"),
        ("a loosened if is rejected", mutated(lambda w: job(w, "publish").update(**{"if": "${{ !inputs.dry_run || true }}"})), "inputs.dry_run"),
        ("a missing concurrency group is rejected", mutated(lambda w: job(w, "publish").pop("concurrency")), "concurrency"),
        ("cancel-in-progress true is rejected", mutated(lambda w: job(w, "publish")["concurrency"].update(**{"cancel-in-progress": True})),
         "concurrency"),
        ("a cancel-in-progress expression is rejected", mutated(
            lambda w: job(w, "publish")["concurrency"].update(**{"cancel-in-progress": "${{ github.event_name == 'push' }}"})), "concurrency"),
        ("a concurrency block with no group is rejected", mutated(lambda w: job(w, "publish").update(concurrency={"cancel-in-progress": False})),
         "concurrency"),
        ("a workflow-level concurrency group satisfies it", mutated(
            lambda w: (job(w, "publish").pop("concurrency"), w.update(concurrency={"group": "g", "cancel-in-progress": False}))), None),
        ("the main-only guard removed from the first step is rejected", mutated(
            lambda w: job(w, "publish")["steps"].pop(0)), "main-only guard"),
        ("a guard that no longer mentions main is rejected", mutated(
            lambda w: job(w, "publish")["steps"][0].update(run="true")), "main-only guard"),
        # --- f: runners and actions ---
        ("a windows runner is rejected", mutated(lambda w: job(w, "build").update(**{"runs-on": "windows-latest"})), "`ubuntu-*`"),
        ("a macos runner is rejected", mutated(lambda w: job(w, "publish").update(**{"runs-on": "macos-latest"})), "`ubuntu-*`"),
        ("a runner list is rejected", mutated(lambda w: job(w, "build").update(**{"runs-on": ["ubuntu-latest"]})), "`ubuntu-*`"),
        ("a self-hosted runner is rejected", mutated(lambda w: job(w, "build").update(**{"runs-on": "self-hosted"})), "`ubuntu-*`"),
        ("an unpinned action tag is rejected", mutated(
            lambda w: job(w, "build")["steps"][0].update(uses="actions/checkout@v7")), "40-character commit SHA"),
        ("a short sha is rejected", mutated(lambda w: job(w, "build")["steps"][0].update(uses="actions/checkout@3d3c42e")),
         "40-character commit SHA"),
        ("an upper-case sha is rejected", mutated(lambda w: job(w, "build")["steps"][0].update(uses=f"actions/checkout@{SHA_A.upper()}")),
         "40-character commit SHA"),
        ("a branch ref is rejected", mutated(lambda w: job(w, "build")["steps"][0].update(uses="actions/checkout@main")),
         "40-character commit SHA"),
        ("a third-party action, even pinned, is rejected", mutated(
            lambda w: job(w, "build")["steps"][0].update(uses=f"some-org/some-action@{SHA_A}")), "40-character commit SHA"),
        ("a local action is rejected", mutated(lambda w: job(w, "build")["steps"][0].update(uses="./.github/actions/x")),
         "40-character commit SHA"),
        ("a docker action is rejected", mutated(lambda w: job(w, "build")["steps"][0].update(uses="docker://alpine:3")),
         "40-character commit SHA"),
        ("a reusable-workflow job is rejected", mutated(lambda w: job(w, "build").update(uses="./.github/workflows/x.yml")), "reusable workflow"),
        ("a pinned actions/* action in a sub-path is accepted", mutated(
            lambda w: job(w, "build")["steps"][0].update(uses=f"actions/cache/restore@{SHA_A}")), None),
        # --- every workflow, with or without an environment job ---
        ("a workflow with no environment job that uses a repository secret is rejected", yaml.safe_load("""
on: {push: {branches: [main]}}
jobs:
  other:
    runs-on: ubuntu-latest
    steps:
      - env: {K: "${{ secrets.SOMETHING }}"}
        run: x
"""), "no `environment:`"),
        ("a workflow with no environment job and only GITHUB_TOKEN passes", yaml.safe_load("""
on: {push: {branches: [main]}}
jobs:
  other:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v7
      - env: {GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}"}
        run: gh issue list
"""), None),
        ("a workflow with no environment job that dumps toJSON(secrets) is rejected", yaml.safe_load("""
on: {push: {branches: [main]}}
jobs:
  other:
    runs-on: ubuntu-latest
    steps:
      - run: echo '${{ toJSON(secrets) }}'
"""), "no `environment:`"),
    ]
    return cases


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
    cases4 = check4_cases()
    for label, workflow, needle in cases4:
        found = all_violations(workflow)
        if needle is None and found:
            failures.append(f"{label}: expected no violation, got {found}")
        elif needle is not None and not any(needle in v for v in found):
            failures.append(f"{label}: expected a violation mentioning {needle!r}, got {found}")
    packaging_cases = installer_cases()
    for label, workflow, needle in packaging_cases:
        found = installer_violations(workflow, "windows-installer.yml")
        if needle is None and found:
            failures.append(f"{label}: expected no violation, got {found}")
        elif needle is not None and not any(needle in v for v in found):
            failures.append(f"{label}: expected {needle!r}, got {found}")
    if failures:
        print("check_workflows self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"check_workflows self-test: {len(cases) + len(cases4) + len(packaging_cases)} cases passed")
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
