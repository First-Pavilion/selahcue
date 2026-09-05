#!/usr/bin/env python3
"""Guards 86akcmzyq's follow-up acceptance criterion (see `.github/pull_request_template.md`'s
"Feature-flag reachability" section): a Cargo feature the product has decided must be reachable
from `make launch` / `make operator` under their DEFAULT (no override) invocation must actually
show up in those targets' resolved `--features` list, or this fails a build instead of relying
on the PR template's unchecked checkbox -- exactly the human step that let 86akby7d8 (sermon
notes, `openai-notes`) ship, merge, pass four-reviewer review, and stay invisible from the one
command a developer actually runs (86akcmzyq's own root cause).

WHAT THIS DOES NOT DECIDE. Which features belong in REQUIRED_DEFAULT_FEATURES below is a
product/owner call (86akcmzrd is the precedent for dev-keys/openai-notes), not something this
script infers from the Makefile it checks -- if it read the requirement back out of the very
`AI_FEATURES := ...` line it verifies, a Makefile edit that silently dropped a feature would have
nothing independent to catch it against. Add a feature to the set only when a decision ticket
says it must be default-reachable the same way, and say so in the commit that adds it.

HOW THE CHECK WORKS. Runs `make -n <target>` (GNU Make's dry run: prints the resolved recipe
text without executing any of it) for both `launch` and `operator`, with AI/STT/RELEASE/
OP_FEATURES cleared from the environment first so the DEFAULT resolution is what gets checked,
not whatever override happened to be exported in the calling shell (Make's `?=` respects an
inherited environment variable exactly like a command-line override). Every `--features
<comma-list>` occurrence anywhere in that dry-run text is unioned into one set -- `launch` builds
the operator crate directly (`cargo build --manifest-path .../selahcue-operator/Cargo.toml
--features ...`) and `operator` shells out to `scripts/run_operator_macapp.sh --features ...`, so
this deliberately does not hardcode either target's exact line shape -- and every required
feature must be an exact comma-split TOKEN in that union, never a substring match: the Makefile's
own `OP_FEATURES_WORDS` comment names `cloud-stt` containing "stt" as a substring as exactly the
trap a naive `in` check would fall into.

CROSS-PLATFORM SCOPE. Wired into CI on Linux only (see `.github/workflows/ci.yml`) -- `make`
itself is only proven cross-OS-reliable in this pipeline's own `nfr` job, which gates its `make
nfr` step the same way with the comment "Windows is a POSIX-script limit"; introducing a new
Windows dependency on GNU Make dry-run parsing is out of scope for this fix. `make ci` runs this
unconditionally, since that always runs on whatever machine the developer is actually on.

Self-test: `check_launch_reachability.py --self-test` exercises the comparison logic against
fixed dry-run-shaped fixtures -- including one built by deleting the required features from a
real fixture, standing in for exactly the Makefile regression this script exists to catch --
without touching the real Makefile or invoking `make`/`cargo` at all, so it runs anywhere. The
real check (`check_launch_reachability.py`, no flag) shells out to the actual `make -n launch` /
`make -n operator` in this repo checkout.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The registry. See the module docstring for why this is not derived from the Makefile.
REQUIRED_DEFAULT_FEATURES = {"dev-keys", "openai-notes"}

TARGETS = ("launch", "operator")

FEATURES_FLAG = re.compile(r"--features\s+(\S+)")


def resolved_features(dry_run_text: str) -> set[str]:
    """Every feature token named in any `--features <list>` occurrence in `dry_run_text`."""
    features: set[str] = set()
    for match in FEATURES_FLAG.finditer(dry_run_text):
        features.update(match.group(1).split(","))
    return features


def missing_features(dry_run_text: str) -> set[str]:
    """The required features that do NOT appear as a token anywhere in `dry_run_text`."""
    return REQUIRED_DEFAULT_FEATURES - resolved_features(dry_run_text)


def run_make_dry(target: str) -> str:
    """`make -n <target>` output, with AI/STT/RELEASE/OP_FEATURES cleared so the DEFAULT
    resolution is what gets checked rather than an override left exported in the calling shell."""
    env = dict(os.environ)
    for var in ("AI", "STT", "RELEASE", "OP_FEATURES"):
        env.pop(var, None)
    result = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"`make -n {target}` itself failed (exit {result.returncode}):", file=sys.stderr)
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SystemExit(1)
    return result.stdout


# --- fixtures for --self-test, modelled on real `make -n launch`/`make -n operator` output ----

FIXTURE_LAUNCH_OK = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt,dev-keys,openai-notes \n"
    'echo ">> AI-assisted sermon notes: on"\n'
)
FIXTURE_OPERATOR_OK = (
    'echo ">> AI-assisted sermon notes: on"\n'
    "sh scripts/run_operator_macapp.sh --features stt,dev-keys,openai-notes\n"
)
# The regression this whole script exists to catch: AI_FEATURES silently dropped from the
# Makefile, leaving only the (unrelated) on-device STT feature reaching the launch targets --
# textually identical to what `make -n launch` prints today if `AI_FEATURES := dev-keys
# openai-notes` is deleted or a future edit stops it reaching OP_FEATURES.
FIXTURE_LAUNCH_REGRESSED = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt \n"
)
# The bare-cargo-run case: no `--features` flag reaches the command line at all (e.g. what `AI=0
# STT=0` resolves to). A regex that matches nothing here must still report BOTH features missing,
# not pass vacuously because it found no `--features` flag to disagree with.
FIXTURE_NO_FEATURES_AT_ALL = "cargo build --manifest-path .../Cargo.toml \n"
# The substring trap the Makefile's own OP_FEATURES_WORDS comment names: `cloud-stt` contains
# "stt" as a substring. Neither required feature is a substring of anything here, so this is a
# clean negative control for the tokenization itself, independent of the AI/STT question.
FIXTURE_SUBSTRING_TRAP = "cargo build --manifest-path .../Cargo.toml --features cloud-stt,ndi \n"


def self_test() -> int:
    cases: list[tuple[str, str, set[str]]] = [
        ("launch OK fixture reports nothing missing", FIXTURE_LAUNCH_OK, set()),
        ("operator OK fixture reports nothing missing", FIXTURE_OPERATOR_OK, set()),
        (
            "AI_FEATURES-dropped fixture reports BOTH features missing",
            FIXTURE_LAUNCH_REGRESSED,
            set(REQUIRED_DEFAULT_FEATURES),
        ),
        (
            "a dry run with no --features flag at all reports both missing, not vacuously OK",
            FIXTURE_NO_FEATURES_AT_ALL,
            set(REQUIRED_DEFAULT_FEATURES),
        ),
        (
            "a substring-only feature list (cloud-stt) does not falsely satisfy "
            "dev-keys/openai-notes",
            FIXTURE_SUBSTRING_TRAP,
            set(REQUIRED_DEFAULT_FEATURES),
        ),
    ]
    failures = []
    for name, fixture, expected_missing in cases:
        actual = missing_features(fixture)
        if actual != expected_missing:
            failures.append(
                f"{name}: expected missing={sorted(expected_missing)}, got={sorted(actual)}"
            )
    if failures:
        print("check_launch_reachability self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"check_launch_reachability self-test: {len(cases)} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    failed = False
    for target in TARGETS:
        dry_run_text = run_make_dry(target)
        missing = missing_features(dry_run_text)
        if missing:
            failed = True
            print(
                f"`make {target}` (default invocation) does not reach: "
                f"{', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            print(
                "  These Cargo features are required to be reachable from `make launch`/`make "
                "operator` by default (86akcmzrd). If dropping one from the default was "
                "intentional, update REQUIRED_DEFAULT_FEATURES in "
                "scripts/check_launch_reachability.py and say why in the commit; if not, this "
                "is the exact regression 86akcmzyq fixed.",
                file=sys.stderr,
            )
    if failed:
        return 1
    print(
        "check_launch_reachability: "
        f"{sorted(REQUIRED_DEFAULT_FEATURES)} reachable from `make launch`/`make operator` "
        "by default"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
