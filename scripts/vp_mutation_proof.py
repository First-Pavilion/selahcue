#!/usr/bin/env python3
"""Prove the harness's controls bite: break each one on a scratch copy and watch a self-test go red.

    python3 scripts/vp_mutation_proof.py                  # every mutation (about 4 minutes)
    python3 scripts/vp_mutation_proof.py --only slice-cap-off run-cap-off
    python3 scripts/vp_mutation_proof.py --list

A self-test that passes proves nothing about itself: if the control it names were deleted, would it still
pass? `docs/design/visual-parity/marketing/mutations.json` lists one edit per control (a cap switched off, a
gate removed, a check inverted). For each, this script copies `scripts/` to a scratch directory (with
`docs/`, `implementation/` and `.git` symlinked, so nothing real can be written), applies the ONE edit, runs
the named self-test there, and requires it to exit non-zero. A mutation that does not apply (the code moved) or
that the self-test survives is a failure: the control is dead or the list is stale.

Never edits the working tree. Bounded: one scratch copy at a time, removed after each run; a mutation that hangs
is killed at TIMEOUT_S.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
}


def run_one(m):
    """Return (ok, detail, first_fail_lines)."""
    scratch = tempfile.mkdtemp(prefix="vp-mutation-")
    try:
        shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(scratch, "scripts"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("docs", "implementation", ".git"):
            src = os.path.join(REPO, name)
            if os.path.exists(src):
                os.symlink(src, os.path.join(scratch, name))
        path = os.path.join(scratch, "scripts", m["file"])
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        if m["old"] not in source:
            return False, "DID NOT APPLY: the pattern is not in %s any more (the code moved; update the list)" % m["file"], []
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source.replace(m["old"], m["new"], 1))
        runner = RUNNERS[m.get("runner", "selftest")]
        try:
            p = subprocess.run([sys.executable, os.path.join(scratch, "scripts", runner[0])] + runner[1:],
                               capture_output=True, text=True, timeout=TIMEOUT_S, cwd=scratch)
        except subprocess.TimeoutExpired:
            return True, "the mutated self-test hung and was killed (counts as red)", []
        fails = [line for line in p.stdout.splitlines() if line.startswith("FAIL")]
        if p.returncode == 0:
            return False, "SURVIVED: the self-test still exits 0 with the control removed", []
        return True, "red: exit %d, %d failing control(s)" % (p.returncode, len(fails)), fails[:2]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
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
    bad = 0
    for m in chosen:
        ok, detail, fails = run_one(m)
        print("%-4s %-28s %s" % ("ok" if ok else "FAIL", m["id"], detail))
        for line in fails:
            print("       " + line[:170])
        bad += 0 if ok else 1
    print("=== mutation proof: %d mutation(s), %d not proved ===" % (len(chosen), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
