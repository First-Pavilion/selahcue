#!/usr/bin/env python3
"""Prove the harness's controls bite: break each one on a scratch copy and watch a self-test go red.

    python3 scripts/vp_mutation_proof.py                  # every mutation (about 4 to 6 minutes)
    python3 scripts/vp_mutation_proof.py --only slice-cap-off run-cap-off
    python3 scripts/vp_mutation_proof.py --list
    python3 scripts/vp_mutation_proof.py --self-check     # prove THIS tool's own guarantees (about 30 seconds)

A self-test that passes proves nothing about itself: if the control it names were deleted, would it still
pass? `docs/design/visual-parity/marketing/mutations.json` lists one edit per control (a cap switched off, a
gate removed, a check inverted). For each, this script builds a scratch directory, applies the ONE edit, runs
the named self-test there, and requires it to exit non-zero.

What counts as NOT proved (the run fails):
  * the pattern is not in the file any more (the code moved), or the self-test still exits 0 (the control is dead);
  * the self-test HANGS past the timeout (a hang proves nothing: it is a failure of the test or of the list);
  * the unmutated scratch copy does not pass its own self-test first (the baseline; otherwise every mutation
    would "go red" for a reason that has nothing to do with the control).

What it guarantees about the real checkout, and how that is made true:
  * The scratch directory holds REAL COPIES of `scripts/`, `docs/` and `implementation/marketing/` (without
    `node_modules/` and `dist/`) and a scratch git repository whose object store reads the real one through
    git's `alternates` file (read-only: git writes new objects to the scratch store). There are NO symlinks into
    the checkout (an earlier version linked `docs/`, `implementation/` and `.git`, and a symlink writes
    through), so nothing a mutated self-test writes can reach the real tree.
  * Belt and braces: the real checkout's HEAD, `git status --porcelain` and a digest of every modified or
    untracked file are taken before the first mutation and compared after the last; a difference fails the run.
    (So do not edit the working tree while it runs.)
  * One scratch copy at a time, removed after each run. A mutation that hangs is killed together with everything
    it started (it runs in its own session, and only that process group is signalled).

`--self-check` proves the guarantees above and the not-proved rules with synthetic cases, and each of its checks
is itself in `mutations.json` (runner `proof-selftest`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MUTATIONS = os.path.join(REPO, "docs", "design", "visual-parity", "marketing", "mutations.json")
TIMEOUT_S = 300
RUNNERS = {
    "selftest": ["vp_selftest.py"],
    "audit-selftest": ["check_fidelity_audit.py", "--self-test"],
    "proof-selftest": ["vp_mutation_proof.py", "--self-check"],
}
# What a scratch copy holds. Everything else (the Rust workspace, mobile, node_modules, dist) is not read by any
# self-test; a self-test that needs a bundle builds its own in a temporary directory.
COPY_DIRS = ("docs", os.path.join("implementation", "marketing"))
SKIP_NAMES = ("node_modules", "dist", "__pycache__", ".visual-parity")

_last_pgid = {"value": None}  # the process group of the most recent runner, for --self-check


def _git(args, cwd, timeout=60):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, timeout=timeout)


def repo_fingerprint(repo):
    """(HEAD, porcelain status, digest of every modified or untracked file's CONTENT) of a git checkout.

    The status alone cannot see a second edit to a file that was already modified; the digest can.
    """
    head = _git(["rev-parse", "HEAD"], repo).stdout.strip()
    porcelain = _git(["status", "--porcelain"], repo).stdout
    listed = _git(["ls-files", "-m", "-o", "--exclude-standard", "-z"], repo).stdout
    digest = hashlib.sha256()
    for rel in sorted(x for x in listed.split("\0") if x):
        digest.update(rel.encode("utf-8", "replace") + b"\0")
        try:
            with open(os.path.join(repo, rel), "rb") as fh:
                digest.update(fh.read())
        except OSError:
            digest.update(b"<unreadable>")
    return head, porcelain, digest.hexdigest()


def guard_problem(before, after):
    """None when the real checkout is unchanged; otherwise one sentence saying what changed."""
    if before == after:
        return None
    names = ("HEAD", "git status", "the content of modified or untracked files")
    what = [name for name, a, b in zip(names, before, after) if a != b]
    return "the real checkout changed while the proof ran (%s)" % ", ".join(what)


def make_scratch(repo=REPO):
    """A scratch directory of REAL COPIES (no symlinks) that a self-test can run in. The caller removes it."""
    scratch = tempfile.mkdtemp(prefix="vp-mutation-")
    shutil.copytree(os.path.join(repo, "scripts"), os.path.join(scratch, "scripts"),
                    ignore=shutil.ignore_patterns(*SKIP_NAMES))
    for rel in COPY_DIRS:
        src = os.path.join(repo, rel)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(scratch, rel), ignore=shutil.ignore_patterns(*SKIP_NAMES))
    # A scratch repository so commit-existence checks work; it READS the real object store through `alternates`.
    _git(["init", "-q"], scratch)
    common = _git(["rev-parse", "--git-common-dir"], repo).stdout.strip()
    if common:
        objects = os.path.join(os.path.abspath(os.path.join(repo, common)), "objects")
        if os.path.isdir(objects):
            info = os.path.join(scratch, ".git", "objects", "info")
            os.makedirs(info, exist_ok=True)
            with open(os.path.join(info, "alternates"), "w", encoding="utf-8") as fh:
                fh.write(objects + "\n")
    return scratch


def run_runner(scratch, runner, timeout):
    """Run a self-test in `scratch`. Returns (returncode, output) or (None, output) when it hung and was killed."""
    p = subprocess.Popen([sys.executable, os.path.join(scratch, "scripts", runner[0])] + runner[1:], cwd=scratch,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    _last_pgid["value"] = p.pid  # start_new_session made this its own process group
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)  # only the group this tool started
        except ProcessLookupError:
            pass
        out, _ = p.communicate()
        return None, out or ""
    return p.returncode, out or ""


def run_one(m, timeout=TIMEOUT_S, repo=REPO):
    """Return (proved, detail, first_fail_lines)."""
    scratch = make_scratch(repo)
    try:
        path = os.path.join(scratch, "scripts", m["file"])
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        if m["old"] not in source:
            return False, "DID NOT APPLY: the pattern is not in %s any more (the code moved; update the list)" % m["file"], []
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source.replace(m["old"], m["new"], 1))
        code, out = run_runner(scratch, RUNNERS[m.get("runner", "selftest")], timeout)
        if code is None:
            return False, "HUNG: the mutated self-test was killed after %ds; a hang proves nothing, so this is NOT proved" % timeout, []
        fails = [line for line in out.splitlines() if line.startswith("FAIL")]
        if code == 0:
            return False, "SURVIVED: the self-test still exits 0 with the control removed", []
        return True, "red: exit %d, %d failing control(s)" % (code, len(fails)), fails[:2]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def baseline_problem(runner_key, timeout=TIMEOUT_S, repo=REPO):
    """None when the UNMUTATED scratch copy passes this runner; otherwise why the proof cannot be trusted."""
    scratch = make_scratch(repo)
    try:
        code, out = run_runner(scratch, RUNNERS[runner_key], timeout)
        if code == 0:
            return None
        if code is None:
            return "the unmutated copy hung (killed after %ds)" % timeout
        fails = [line for line in out.splitlines() if line.startswith("FAIL")]
        return "the unmutated copy already fails (exit %d): %s" % (code, fails[0][:150] if fails else out[-150:].strip())
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------------------
# --self-check: this tool's own guarantees, on synthetic cases
# ---------------------------------------------------------------------------------------------------------------

def self_check():
    failures = []

    def ok(cond, label):
        print("%s: %s" % ("PASS" if cond else "FAIL", label), flush=True)
        if not cond:
            failures.append(label)

    # 1. a mutation that hangs is NOT proved, and nothing it started survives
    hang = {"id": "x", "file": "check_fidelity_audit.py", "runner": "audit-selftest",
            "old": "from __future__ import annotations\n",
            "new": "from __future__ import annotations\nimport time as _t\n_t.sleep(10**6)\n"}
    proved, detail, _f = run_one(hang, timeout=15)
    pgid = _last_pgid["value"]
    gone = False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        gone = True
    except PermissionError:
        gone = False
    ok(proved is False and detail.startswith("HUNG"), "a mutation whose self-test hangs is NOT proved (%s)" % detail[:60])
    ok(gone, "the hung self-test's whole process group was killed")

    # 2. the other not-proved outcomes and the proved one
    noop = {"id": "x", "file": "check_fidelity_audit.py", "runner": "audit-selftest",
            "old": "from __future__ import annotations\n", "new": "from __future__ import annotations\n"}
    proved, detail, _f = run_one(noop)
    ok(proved is False and detail.startswith("SURVIVED"), "a mutation the self-test survives is NOT proved (%s)" % detail[:40])
    proved, detail, _f = run_one(dict(noop, old="this text is not in the file"))
    ok(proved is False and detail.startswith("DID NOT APPLY"), "a mutation that does not apply is NOT proved (%s)" % detail[:40])
    real = dict(noop, old="    if _is_shallow(repo):\n        return None", new="    if False:\n        return None")
    proved, detail, _f = run_one(real)
    ok(proved is True and detail.startswith("red"), "a mutation the self-test catches IS proved (%s)" % detail[:40])
    ok(baseline_problem("audit-selftest") is None, "the unmutated copy passes its baseline")

    # 3. the scratch copy shares nothing with the checkout
    scratch = make_scratch()
    try:
        links = [os.path.join(d, n) for d, dirs, files in os.walk(scratch) for n in dirs + files
                 if os.path.islink(os.path.join(d, n))]
        ok(not links, "the scratch copy has no symlinks into the checkout (%d found)" % len(links))
        marker = os.path.join(scratch, "docs", "design", "vp-mutation-selfcheck.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("written into the scratch copy")
        ok(not os.path.exists(os.path.join(REPO, "docs", "design", "vp-mutation-selfcheck.txt")),
           "a file written into the scratch docs/ does not appear in the real docs/")
        ok(os.path.isdir(os.path.join(scratch, "scripts")) and os.path.isdir(os.path.join(scratch, "docs"))
           and os.path.isdir(os.path.join(scratch, "implementation", "marketing", "src")),
           "the scratch copy holds scripts/, docs/ and implementation/marketing/src")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # 4. the real-checkout guard sees a new file, a SECOND edit to an already-modified file, and a new commit
    tmp = tempfile.mkdtemp(prefix="vp-guard-")
    try:
        ident = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        _git(["init", "-q"], tmp)
        with open(os.path.join(tmp, "a.txt"), "w") as fh:
            fh.write("one\n")
        _git(["add", "a.txt"], tmp)
        _git(ident + ["commit", "-q", "-m", "first"], tmp)
        base = repo_fingerprint(tmp)
        ok(guard_problem(base, repo_fingerprint(tmp)) is None, "the guard is quiet when nothing changed")
        with open(os.path.join(tmp, "new.txt"), "w") as fh:
            fh.write("untracked\n")
        ok(guard_problem(base, repo_fingerprint(tmp)) is not None, "the guard sees a new untracked file")
        os.remove(os.path.join(tmp, "new.txt"))
        with open(os.path.join(tmp, "a.txt"), "w") as fh:
            fh.write("two\n")
        modified = repo_fingerprint(tmp)
        with open(os.path.join(tmp, "a.txt"), "w") as fh:
            fh.write("three\n")
        ok(guard_problem(modified, repo_fingerprint(tmp)) is not None,
           "the guard sees a second edit to a file that was already modified (the status text alone cannot)")
        _git(ident + ["commit", "-q", "-am", "second"], tmp)
        ok(guard_problem(base, repo_fingerprint(tmp)) is not None, "the guard sees a new commit")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("=== vp_mutation_proof self-check: %d failure(s) ===" % len(failures))
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-check", action="store_true", help="prove this tool's own guarantees")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S, help="seconds before a mutated self-test counts as hung")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    with open(MUTATIONS, "r", encoding="utf-8") as fh:
        muts = json.load(fh)["mutations"]
    if args.list:
        for m in muts:
            print("%-28s %-26s %s" % (m["id"], m["file"], m.get("control", "")))
        return 0
    chosen = [m for m in muts if not args.only or m["id"] in args.only]
    if args.only and len(chosen) != len(set(args.only)):
        print("FAIL: unknown mutation id(s): %s" % ", ".join(sorted(set(args.only) - {m["id"] for m in chosen})))
        return 2
    before = repo_fingerprint(REPO)
    for key in sorted({m.get("runner", "selftest") for m in chosen}):
        problem = baseline_problem(key, args.timeout)
        print("%-4s baseline [%s] %s" % ("ok" if problem is None else "FAIL", key, problem or "the unmutated copy passes"), flush=True)
        if problem:
            print("=== mutation proof: stopped, the baseline is not green so no mutation can be proved ===")
            return 1
    bad = 0
    for m in chosen:
        proved, detail, fails = run_one(m, args.timeout)
        print("%-4s %-28s %s" % ("ok" if proved else "FAIL", m["id"], detail), flush=True)
        for line in fails:
            print("       " + line[:170])
        bad += 0 if proved else 1
    changed = guard_problem(before, repo_fingerprint(REPO))
    print("%-4s real checkout untouched %s" % ("ok" if changed is None else "FAIL",
                                              "(HEAD %s)" % before[0][:8] if changed is None else changed))
    print("=== mutation proof: %d mutation(s), %d not proved%s ===" % (len(chosen), bad, "" if changed is None else ", CHECKOUT CHANGED"))
    return 1 if (bad or changed) else 0


if __name__ == "__main__":
    sys.exit(main())
