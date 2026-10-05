#!/usr/bin/env python3
"""The minute rules of CI (17tnw2b2nxk), as a check that can fail.

This repository is private on the GitHub Team plan: 3,000 included minutes a month, Linux x1,
Windows x2, macOS x10, and with no payment method every job is BLOCKED once the quota is gone.
Measured on 100 runs, macOS was 64% of the bill and Windows 19%. The owner decided on
2026-10-05 that macOS leaves CI entirely and that Windows runs weekly or on demand. Each rule
below is one careless edit away from undoing that, and none of them is a thing actionlint or
check_workflows.py looks at. Run from the repository root; it reads .github/workflows.

1. NO MACOS RUNNER, ANYWHERE. Any `macos` in a job's `runs-on` or `strategy.matrix`, in any
   workflow, is refused. A matrix copied from an older example is the likely way back.
2. WINDOWS ONLY THROUGH THE TIER. In a workflow that runs on pull_request, push or schedule, a
   job may not name a Windows runner literally. The matrices of ci.yml get Windows only from
   `needs.changes.outputs.os`, which the `tier` step computes. (A dispatch-only workflow such
   as windows-installer.yml is exempt: it costs minutes only when somebody clicks Run.)
3. THE TIER STEP BEHAVES. The `run:` text of the `tier` step in ci.yml's `changes` job is EXECUTED
   here, with the environment each event type provides, and its outputs are compared to the rule:
   Windows for schedule, a release tag, a dispatch with the input on, and a pull request with the
   `full-ci` label; Linux only for everything else; every area for schedule, dispatch and tags.
   This reads the real step, so an edit that, say, turns Windows on for every pull request fails
   here, on the pull request that makes it.
4. THE ALARM KNOWS THE MATRIX JOBS. The jobs whose matrix comes from the tier output must be
   exactly `MATRIX_JOBS` in ci_alarm.py (a matrix job missing there would let a Linux-only
   success clear a Windows failure), each must be in the `ci-alarm` job's `needs`, and each must
   spell its matrix exactly `fromJSON(needs.changes.outputs.os || '["ubuntu-latest"]')`: without
   the fallback a run whose `changes` job was skipped (a label other than full-ci) would fail to
   evaluate the matrix instead of skipping.
5. SUPERSEDED PULL-REQUEST RUNS ARE CANCELLED. ci.yml has a workflow-level `concurrency` whose
   `cancel-in-progress` is exactly `${{ github.event_name == 'pull_request' }}` (never a main
   run: every main commit keeps its verdict).

What it does not do: it does not read the bill. The numbers are in the pull request that
introduced it and in CLAUDE.md. It does not stop a workflow file from being added with a
trigger this script has not heard of; rules 1 and 2 apply to every workflow in the directory.

Self-test: `check_ci_minutes.py --self-test`.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

import yaml

from ci_alarm import MATRIX_JOBS

CI_WORKFLOW = ".github/workflows/ci.yml"
COST_TRIGGERS = {"pull_request", "pull_request_target", "push", "schedule"}
TIER_EXPR = "needs.changes.outputs.os"
# The one spelling of the matrix. The fallback matters: when `changes` is skipped (a label other
# than full-ci) its output is empty, and fromJSON('') is an evaluation error that would turn the
# skipped run into a failed one. Linux only is the cheap, stricter reading.
MATRIX_EXPR = "${{ fromJSON(needs.changes.outputs.os || '[\"ubuntu-latest\"]') }}"
CANCEL_EXPR = "${{ github.event_name == 'pull_request' }}"
MACOS = re.compile(r"mac\s*-?\s*os", re.I)
WINDOWS = re.compile(r"windows", re.I)


def triggers(workflow: dict) -> set[str]:
    """Event names. PyYAML (YAML 1.1) loads the bare key `on` as the boolean True."""
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, (list, dict)):
        return {str(e) for e in on}
    return set()


def strings(value) -> list[str]:
    """Every string anywhere inside `value`, keys included."""
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in value.items():
            out += strings(k) + strings(v)
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out += strings(v)
        return out
    return [] if value is None or isinstance(value, bool) else [str(value)]


def runner_strings(job: dict) -> list[str]:
    matrix = (job.get("strategy") or {}).get("matrix") if isinstance(job.get("strategy"), dict) else None
    return strings(job.get("runs-on")) + strings(matrix)


def runner_violations(workflow: dict, filename: str) -> list[str]:
    """Rules 1 and 2."""
    out = []
    costly = bool(triggers(workflow) & COST_TRIGGERS)
    for name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for s in runner_strings(job):
            if MACOS.search(s):
                out.append(
                    f"{filename}: job `{name}` names a macOS runner (`{s}`). macOS is not in CI "
                    f"(17tnw2b2nxk): it bills 10 minutes per minute, and the owner's local `make ci` "
                    f"is the macOS gate."
                )
            if costly and WINDOWS.search(s) and "${{" not in s:
                out.append(
                    f"{filename}: job `{name}` names a Windows runner literally (`{s}`) in a workflow "
                    f"that runs on pull_request, push or schedule. Windows bills 2x and is added "
                    f"only by the tier step, through `{TIER_EXPR}`."
                )
    return out


def tier_matrix_jobs(workflow: dict) -> set[str]:
    out = set()
    for name, job in (workflow.get("jobs") or {}).items():
        matrix = (job.get("strategy") or {}).get("matrix") if isinstance(job, dict) and isinstance(job.get("strategy"), dict) else None
        if isinstance(matrix, dict) and TIER_EXPR in str(matrix.get("os", "")):
            out.add(name)
    return out


def alarm_violations(workflow: dict, filename: str) -> list[str]:
    """Rule 4."""
    jobs = workflow.get("jobs") or {}
    found = tier_matrix_jobs(workflow)
    out = []
    if found != set(MATRIX_JOBS):
        out.append(
            f"{filename}: the jobs whose matrix comes from `{TIER_EXPR}` are {sorted(found)}, but "
            f"MATRIX_JOBS in .github/scripts/ci_alarm.py is {sorted(MATRIX_JOBS)}. A matrix job the "
            f"alarm does not know lets a Linux-only success clear a Windows failure. Make them agree."
        )
    needs = (jobs.get("ci-alarm") or {}).get("needs")
    needs = needs if isinstance(needs, list) else ([needs] if needs else [])
    for name in sorted(found - set(needs)):
        out.append(f"{filename}: matrix job `{name}` is not in the `ci-alarm` job's `needs`, so its failure on main is invisible.")
    for name in sorted(found):
        spelled = str(jobs[name]["strategy"]["matrix"].get("os", "")).strip()
        if spelled != MATRIX_EXPR:
            out.append(
                f"{filename}: job `{name}` spells its matrix `{spelled}`; the one accepted spelling is "
                f"`{MATRIX_EXPR}` (the fallback keeps a run with a skipped `changes` job from failing)."
            )
    return out


def concurrency_violations(workflow: dict, filename: str) -> list[str]:
    """Rule 5."""
    conc = workflow.get("concurrency")
    if not isinstance(conc, dict) or str(conc.get("cancel-in-progress", "")).strip() != CANCEL_EXPR:
        return [
            f"{filename}: the workflow-level `concurrency.cancel-in-progress` must be exactly "
            f"`{CANCEL_EXPR}`, so rapid pushes to a pull request do not stack runs and a main run is "
            f"never cancelled. Got: {conc!r}."
        ]
    return []


# ----------------------------------------------------------------------------------------------
# Rule 3: run the tier step.
# ----------------------------------------------------------------------------------------------
LINUX = ["ubuntu-latest"]
BOTH = ["ubuntu-latest", "windows-latest"]
# (label, env, expected os, expected everything)
TIER_CASES = [
    ("pull request, no label", {"EVENT": "pull_request", "REF": "refs/pull/7/merge", "HAS_FULL_CI_LABEL": "false"}, LINUX, "false"),
    ("pull request, full-ci label", {"EVENT": "pull_request", "REF": "refs/pull/7/merge", "HAS_FULL_CI_LABEL": "true"}, BOTH, "false"),
    ("pull request, label output garbled", {"EVENT": "pull_request", "REF": "refs/pull/7/merge", "HAS_FULL_CI_LABEL": "true; echo x"}, LINUX, "false"),
    ("push to main", {"EVENT": "push", "REF": "refs/heads/main"}, LINUX, "false"),
    ("push to another branch", {"EVENT": "push", "REF": "refs/heads/feature"}, LINUX, "false"),
    ("push of a release tag", {"EVENT": "push", "REF": "refs/tags/v1.2.3"}, BOTH, "true"),
    ("weekly schedule", {"EVENT": "schedule", "REF": "refs/heads/main"}, BOTH, "true"),
    ("dispatch, windows off", {"EVENT": "workflow_dispatch", "REF": "refs/heads/main", "DISPATCH_WINDOWS": "false"}, LINUX, "true"),
    ("dispatch, windows input empty", {"EVENT": "workflow_dispatch", "REF": "refs/heads/main", "DISPATCH_WINDOWS": ""}, LINUX, "true"),
    ("dispatch, windows on", {"EVENT": "workflow_dispatch", "REF": "refs/heads/feature", "DISPATCH_WINDOWS": "true"}, BOTH, "true"),
    ("an event nobody planned for", {"EVENT": "repository_dispatch", "REF": "refs/heads/main"}, LINUX, "false"),
]


def tier_script(workflow: dict) -> str | None:
    steps = ((workflow.get("jobs") or {}).get("changes") or {}).get("steps") or []
    for step in steps:
        if isinstance(step, dict) and step.get("id") == "tier":
            return str(step.get("run", ""))
    return None


def run_tier(script: str, env: dict[str, str]) -> tuple[dict[str, str], int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        out_file = os.path.join(tmp, "output")
        summary = os.path.join(tmp, "summary")
        for p in (out_file, summary):
            open(p, "w").close()
        full_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_OUTPUT": out_file, "GITHUB_STEP_SUMMARY": summary, **env}
        # `bash -e`, as the runner runs a bash `run:` step (-e, and pipefail via -o).
        proc = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script], env=full_env, capture_output=True, text=True)
        outputs = {}
        with open(out_file) as fh:
            for line in fh.read().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    outputs[k] = v
        return outputs, proc.returncode, proc.stderr


def tier_violations(workflow: dict, filename: str) -> list[str]:
    """Rule 3."""
    script = tier_script(workflow)
    if script is None:
        return [f"{filename}: no step with `id: tier` in the `changes` job, so nothing decides whether Windows runs."]
    out = []
    for label, env, want_os, want_everything in TIER_CASES:
        outputs, rc, err = run_tier(script, env)
        if rc != 0:
            out.append(f"{filename}: the tier step exited {rc} for {label}: {err.strip()[:200]}")
            continue
        try:
            got_os = json.loads(outputs.get("os", "null"))
        except ValueError:
            got_os = outputs.get("os")
        if got_os != want_os or outputs.get("everything") != want_everything or outputs.get("windows") != str("windows-latest" in want_os).lower():
            out.append(
                f"{filename}: the tier step gave os={outputs.get('os')} everything={outputs.get('everything')} "
                f"windows={outputs.get('windows')} for {label}; expected os={json.dumps(want_os, separators=(',', ':'))} "
                f"everything={want_everything}."
            )
    return out


def all_violations(workflows: dict[str, dict]) -> list[str]:
    out = []
    for path, wf in workflows.items():
        out += runner_violations(wf, path)
    ci = workflows.get(CI_WORKFLOW)
    if ci is None:
        out.append(f"{CI_WORKFLOW}: not found (run from the repository root).")
    else:
        out += tier_violations(ci, CI_WORKFLOW) + alarm_violations(ci, CI_WORKFLOW) + concurrency_violations(ci, CI_WORKFLOW)
    return out


# ----------------------------------------------------------------------------------------------
# Self-test.
# ----------------------------------------------------------------------------------------------
GOOD_TIER = r"""
windows=false
everything=false
case "$EVENT" in
  schedule) windows=true; everything=true ;;
  workflow_dispatch)
    everything=true
    if [ "$DISPATCH_WINDOWS" = "true" ]; then windows=true; fi ;;
  push)
    case "$REF" in refs/tags/*) windows=true; everything=true ;; esac ;;
  pull_request)
    if [ "$HAS_FULL_CI_LABEL" = "true" ]; then windows=true; fi ;;
esac
if [ "$windows" = "true" ]; then os='["ubuntu-latest","windows-latest"]'; else os='["ubuntu-latest"]'; fi
{ echo "windows=$windows"; echo "everything=$everything"; echo "os=$os"; } >> "$GITHUB_OUTPUT"
"""


def synthetic(script: str = GOOD_TIER, *, extra_matrix: str | None = None, alarm_needs=("rust", "operator", "operator-native"),
              cancel: str = CANCEL_EXPR, on=None, launch_os="[ubuntu-latest]") -> dict:
    expr = MATRIX_EXPR
    jobs = {
        "changes": {"steps": [{"id": "tier", "run": script}]},
        "rust": {"strategy": {"matrix": {"os": expr}}, "runs-on": "${{ matrix.os }}"},
        "operator": {"strategy": {"matrix": {"os": expr}}, "runs-on": "${{ matrix.os }}"},
        "operator-native": {"strategy": {"matrix": {"os": expr}}, "runs-on": "${{ matrix.os }}"},
        "launch-smoke": {"strategy": {"matrix": {"os": yaml.safe_load(launch_os)}}, "runs-on": "${{ matrix.os }}"},
        "ci-alarm": {"needs": list(alarm_needs)},
    }
    if extra_matrix:
        jobs["extra"] = {"strategy": {"matrix": {"os": expr}}, "runs-on": "${{ matrix.os }}"}
    return {"on": on if on is not None else {"push": {}, "pull_request": {}, "schedule": [{"cron": "0 0 * * 0"}]},
            "concurrency": {"group": "g", "cancel-in-progress": cancel}, "jobs": jobs}


def self_test() -> int:
    failures = []

    def check(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, wanted {want!r}")

    def count(wf):
        return len(runner_violations(wf, "x")) + len(tier_violations(wf, "x")) + len(alarm_violations(wf, "x")) + len(concurrency_violations(wf, "x"))

    check("a conforming workflow is accepted", count(synthetic()), 0)

    # Rule 1
    check("a macos-latest literal in launch-smoke is rejected", count(synthetic(launch_os="[ubuntu-latest, macos-latest]")), 1)
    wf = synthetic()
    wf["jobs"]["x"] = {"runs-on": "macos-14"}
    check("a macos runs-on is rejected", len(runner_violations(wf, "x")), 1)
    wf = synthetic()
    wf["jobs"]["x"] = {"runs-on": "macOS-latest"}
    check("the spelling macOS-latest is rejected", len(runner_violations(wf, "x")), 1)
    wf = synthetic(on={"workflow_dispatch": {}})
    wf["jobs"]["x"] = {"runs-on": "macos-latest"}
    check("macOS is rejected even in a dispatch-only workflow", len(runner_violations(wf, "x")), 1)
    wf = synthetic()
    wf["jobs"]["x"] = {"runs-on": "ubuntu-latest", "steps": [{"name": "macOS note", "run": "echo macos"}]}
    check("the word macOS in a step is not a runner", len(runner_violations(wf, "x")), 0)

    # Rule 2
    wf = synthetic()
    wf["jobs"]["x"] = {"runs-on": "windows-latest"}
    check("a literal windows-latest on a pull-request workflow is rejected", len(runner_violations(wf, "x")), 1)
    wf = synthetic()
    wf["jobs"]["rust"]["strategy"]["matrix"]["os"] = ["ubuntu-latest", "windows-latest"]
    check("a literal Windows leg in a matrix is rejected", len(runner_violations(wf, "x")), 1)
    wf = synthetic(on={"workflow_dispatch": {}})
    wf["jobs"]["x"] = {"runs-on": "windows-latest"}
    check("a dispatch-only Windows workflow is exempt", len(runner_violations(wf, "x")), 0)
    wf = synthetic(on={"schedule": [{"cron": "0 0 * * 0"}]})
    wf["jobs"]["x"] = {"runs-on": "windows-latest"}
    check("a scheduled Windows job is rejected (schedule is a cost trigger)", len(runner_violations(wf, "x")), 1)

    # Rule 3: break the tier step in the ways that matter.
    bad_pr = GOOD_TIER.replace('if [ "$HAS_FULL_CI_LABEL" = "true" ]; then windows=true; fi', "windows=true")
    check("Windows for every pull request is caught", len(tier_violations(synthetic(bad_pr), "x")) >= 1, True)
    bad_push = GOOD_TIER.replace("refs/tags/*", "*")
    check("Windows for every push is caught", len(tier_violations(synthetic(bad_push), "x")) >= 1, True)
    no_label = GOOD_TIER.replace('if [ "$HAS_FULL_CI_LABEL" = "true" ]; then windows=true; fi', ":")
    check("a label that does nothing is caught", len(tier_violations(synthetic(no_label), "x")) >= 1, True)
    no_sched = GOOD_TIER.replace("schedule) windows=true; everything=true ;;", "schedule) ;;")
    check("a weekly run that runs nothing extra is caught", len(tier_violations(synthetic(no_sched), "x")) >= 1, True)
    no_dispatch = GOOD_TIER.replace('if [ "$DISPATCH_WINDOWS" = "true" ]; then windows=true; fi', ":")
    check("a dispatch input that does nothing is caught", len(tier_violations(synthetic(no_dispatch), "x")) >= 1, True)
    path_filtered_week = GOOD_TIER.replace("schedule) windows=true; everything=true ;;", "schedule) windows=true ;;")
    check("a weekly run still path-filtered is caught", len(tier_violations(synthetic(path_filtered_week), "x")) >= 1, True)
    check("a missing tier step is caught", len(tier_violations({"jobs": {"changes": {"steps": []}}}, "x")), 1)
    check("a tier step that exits non-zero is caught", len(tier_violations(synthetic("exit 3"), "x")) >= 1, True)

    # Rule 4
    check("a matrix job the alarm does not know is caught", len(alarm_violations(synthetic(extra_matrix="1"), "x")), 2)
    check("a matrix job missing from the alarm's needs is caught", len(alarm_violations(synthetic(alarm_needs=("rust", "operator")), "x")), 1)
    wf = synthetic()
    del wf["jobs"]["operator-native"]
    check("an alarm registry entry with no such job is caught", len(alarm_violations(wf, "x")), 1)
    wf = synthetic()
    wf["jobs"]["operator"]["strategy"]["matrix"]["os"] = "${{ fromJSON(needs.changes.outputs.os) }}"
    check("a matrix without the Linux-only fallback is caught", len(alarm_violations(wf, "x")), 1)

    # Rule 5
    check("cancel-in-progress: true is rejected (it would cancel main)", len(concurrency_violations(synthetic(cancel="true"), "x")), 1)
    check("no concurrency block is rejected", len(concurrency_violations({"jobs": {}}, "x")), 1)
    check("a spelling with other whitespace is rejected (one spelling)", len(concurrency_violations(synthetic(cancel="${{github.event_name=='pull_request'}}"), "x")), 1)

    # The real workflow files, loaded the way main() does, must be accepted: the positive control
    # that proves the rules are not simply rejecting everything.
    real = load_workflows()
    check("the real workflows are accepted", all_violations(real), [])
    mutated = copy.deepcopy(real)
    mutated[CI_WORKFLOW]["jobs"]["launch-smoke"]["strategy"]["matrix"]["os"] = ["ubuntu-latest", "macos-latest"]
    check("the real ci.yml with a macOS leg added is rejected", len(all_violations(mutated)), 1)

    if failures:
        print("check_ci_minutes self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("check_ci_minutes self-test: all cases passed")
    return 0


def load_workflows() -> dict[str, dict]:
    paths = sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
    out = {}
    for path in paths:
        with open(path) as fh:
            out[path] = yaml.safe_load(fh) or {}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    workflows = load_workflows()
    if not workflows:
        print("no workflows found: run from the repository root", file=sys.stderr)
        return 1
    found = all_violations(workflows)
    if found:
        print("minute rules FAILED:", file=sys.stderr)
        for v in found:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"minute rules: {len(workflows)} workflow(s) OK (no macOS; Windows only via the tier; "
          f"matrix jobs {sorted(MATRIX_JOBS)} known to the alarm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
