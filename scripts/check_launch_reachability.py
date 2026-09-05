#!/usr/bin/env python3
"""Guards 86akcmzyq's follow-up acceptance criterion (see `.github/pull_request_template.md`'s
"Feature-flag reachability" section): a Cargo feature the product has decided must be reachable
from `make launch` / `make operator` under their DEFAULT (no override) invocation must actually
show up in those targets' resolved `--features` list, or this fails a build instead of relying
on the PR template's unchecked checkbox -- exactly the human step that let 86akby7d8 (sermon
notes, `openai-notes`) ship, merge, pass four-reviewer review, and stay invisible from the one
command a developer actually runs (86akcmzyq's own root cause).

THIS HAPPENED A SECOND TIME BEFORE THIS SCRIPT EVEN SHIPPED (86akby7th, `cloud-stt`, closed by
86akd10dq): PR #24 (this script) was authored before PR #22 (`cloud-stt`) merged, so the
then-hardcoded `REQUIRED_DEFAULT_FEATURES = {"dev-keys", "openai-notes"}` had no way to know
`cloud-stt` existed, let alone that it needed the same guarantee -- the check passed green while
Cloud transcription was exactly as unreachable as sermon notes had been. A hand-maintained set in
a script three directories away from the feature it describes is the same shape of hole as the PR
template's unchecked box: both rely on a human remembering a SEPARATE action in a SEPARATE place.
See DERIVATION below for how this version closes that.

DERIVATION (86akd10dq). The required set is no longer a literal set in this file. It is derived
by reading `selahcue-operator/Cargo.toml`'s own `[features]` table and requiring every feature
there (other than `default`) to carry a `# LAUNCH_REACHABILITY: <TAG>` line in its own comment
block -- the same comment block that already has to explain, in prose, why the feature defaults
off. Three tags, and what each means:

  * `REQUIRED` -- a product/owner decision (86akcmzrd is the precedent) that this feature must
    show up in `make launch`/`make operator`'s DEFAULT resolved `--features` list, unconditionally
    (modulo an explicit `AI=0`/`STT=0`/`RELEASE=1` override). Feeds this script's required set.
  * `AUTO` -- reachable only when a local probe succeeds (e.g. `stt`: cmake on PATH), by design.
    Not required, because nobody has made the owner call that this must work with no toolchain.
  * `OPT-IN` -- no dev launch target auto-enables this; reachable only via an explicit
    `OP_FEATURES=` override. Typically because the thing it talks to (a live endpoint, say) does
    not exist yet, so there is nothing for a default `make launch` to usefully reach.

A feature with NO tag, or an unrecognised one, is a HARD FAILURE of this script -- not a silent
"assume not required". This is the actual fix, not the relocation: today, a new off-by-default
feature can land with no reachability decision recorded anywhere and nothing objects. After this
change, it cannot -- the gate that already runs on every `make ci` and every CI push refuses to
pass until someone tags it, which forces the decision to be made (and recorded, in the one file a
reviewer is already looking at for this exact feature) in the SAME PR that adds the feature,
rather than in a follow-up commit to an unrelated script that is easy to forget entirely.

WHY THIS STILL ISN'T READ BACK OUT OF THE MAKEFILE. Cargo.toml and the Makefile are two
independently-authored files -- reading the requirement from Cargo.toml still means a Makefile
edit that silently drops a REQUIRED feature from OP_FEATURES has something independent to fail
against, which is the property the original design was protecting and that reading the Makefile's
own `AI_FEATURES := ...` line back at itself would have destroyed. Deriving from Cargo.toml does
not have that problem: the two files disagreeing is exactly the regression this script exists to
catch.

HOW THE CHECK WORKS. Runs `make -n <target>` (GNU Make's dry run: prints the resolved recipe
text without executing any of it) for both `launch` and `operator`, with AI/STT/RELEASE/
OP_FEATURES cleared from the environment first so the DEFAULT resolution is what gets checked,
not whatever override happened to be exported in the calling shell (Make's `?=` respects an
inherited environment variable exactly like a command-line override). Every `--features
<comma-list>` occurrence anywhere in that dry-run text is unioned into one set -- `launch` builds
the operator crate directly (`cargo build --manifest-path .../selahcue-operator/Cargo.toml
--features ...`) and `operator` shells out to `scripts/run_operator_macapp.sh --features ...`, so
this deliberately does not hardcode either target's exact line shape -- and every REQUIRED
feature must be an exact comma-split TOKEN in that union, never a substring match: the Makefile's
`stt-preflight`/`OP_FEATURES_WORDS` comments name `cloud-stt` containing "stt" as a substring as
exactly the trap a naive `in` check would fall into.

CROSS-PLATFORM SCOPE. Wired into CI on Linux and macOS (see `.github/workflows/ci.yml`), Windows
excluded. Originally Linux-only, citing this pipeline's `nfr` job as precedent for "make is not
cross-OS-reliable" -- PR #24 remediation (86akcmzyq) tested that precedent and found it did not
hold: `nfr`'s macOS skip is about a one-time recorded timing baseline and its Windows skip is
about a POSIX shell script doing memory measurement, neither of which bears on Make itself being
unreliable cross-OS. The feature computation this script inspects has zero $(UNAME)-conditional
branching (verified by reading the Makefile) -- the only OS-conditional code there picks NDI
library paths and which shell wrapper launches the operator, not which Cargo features get
requested -- and every self-test mutation below also passes running this script on macOS.
Windows stays excluded because GNU Make dry-run parsing on that runner is unproven, unlike Linux
and macOS which both ship `make` by default. `make ci` runs this unconditionally, since that
always runs on whatever machine the developer is actually on.

Self-test: `check_launch_reachability.py --self-test` exercises the comparison logic AND the
Cargo.toml tag parser against fixed fixtures -- including one built by deleting a required
feature from a real dry-run fixture (the original regression), and several built by deleting or
corrupting a `LAUNCH_REACHABILITY` tag from a fixture `[features]` block (the 86akby7th
regression this version specifically closes) -- without touching the real Makefile, the real
Cargo.toml, or invoking `make`/`cargo` at all, so it runs anywhere. The real check
(`check_launch_reachability.py`, no flag) reads the real `selahcue-operator/Cargo.toml` and
shells out to the actual `make -n launch` / `make -n operator` in this repo checkout.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

OPERATOR_CARGO_TOML = (
    REPO_ROOT
    / "implementation"
    / "desktop"
    / "crates"
    / "selahcue-operator"
    / "Cargo.toml"
)

# The three reachability decisions a feature's own comment block can declare. See DERIVATION in
# the module docstring for what each means and why an untagged feature is a hard failure rather
# than a silent default.
VALID_TAGS = {"REQUIRED", "AUTO", "OPT-IN"}

TARGETS = ("launch", "operator")

FEATURES_FLAG = re.compile(r"--features\s+(\S+)")
FEATURE_DEF = re.compile(r"^([A-Za-z0-9_-]+)\s*=")
REACHABILITY_TAG = re.compile(r"^#\s*LAUNCH_REACHABILITY:\s*(\S+)")


def parse_feature_tags(cargo_toml_text: str) -> tuple[dict[str, str], list[str]]:
    """Every non-`default` feature declared in the `[features]` table of an operator-shaped
    Cargo.toml, mapped to its `LAUNCH_REACHABILITY` tag -- plus a list of human-readable problems
    for any feature whose comment block has no tag, more than one, or an unrecognised one.

    Deliberately line-based rather than a TOML parser: a TOML parser would discard the very
    comments this function exists to read. The contract this depends on: the tag line sits
    somewhere in the CONTIGUOUS block of `#`-prefixed lines immediately above the feature's own
    `name = [...]` line, with nothing but comment lines between them.
    """
    lines = cargo_toml_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "[features]")
    except StopIteration:
        return {}, ["no `[features]` table found in the Cargo.toml text"]

    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s != "[features]":
            end = i
            break

    tags: dict[str, str] = {}
    problems: list[str] = []
    i = start + 1
    while i < end:
        m = FEATURE_DEF.match(lines[i])
        if m:
            name = m.group(1)
            if name != "default":
                block: list[str] = []
                j = i - 1
                while j > start and lines[j].strip().startswith("#"):
                    block.append(lines[j].strip())
                    j -= 1
                found = [
                    tm.group(1) for line in reversed(block) if (tm := REACHABILITY_TAG.match(line))
                ]
                if not found:
                    problems.append(
                        f"`{name}` has no `LAUNCH_REACHABILITY:` tag in its comment block"
                    )
                elif len(found) > 1:
                    problems.append(
                        f"`{name}` has {len(found)} `LAUNCH_REACHABILITY:` tags in its comment "
                        f"block (ambiguous): {found}"
                    )
                elif found[0] not in VALID_TAGS:
                    problems.append(
                        f"`{name}`'s `LAUNCH_REACHABILITY:` tag {found[0]!r} is not one of "
                        f"{sorted(VALID_TAGS)}"
                    )
                else:
                    tags[name] = found[0]
        i += 1
    return tags, problems


def required_from_tags(tags: dict[str, str]) -> set[str]:
    """Features tagged `REQUIRED` -- the set this script asserts is reachable by default."""
    return {name for name, tag in tags.items() if tag == "REQUIRED"}


def resolved_features(dry_run_text: str) -> set[str]:
    """Every feature token named in any `--features <list>` occurrence in `dry_run_text`."""
    features: set[str] = set()
    for match in FEATURES_FLAG.finditer(dry_run_text):
        features.update(match.group(1).split(","))
    return features


def missing_features(dry_run_text: str, required: set[str]) -> set[str]:
    """The `required` features that do NOT appear as a token anywhere in `dry_run_text`."""
    return required - resolved_features(dry_run_text)


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
# Deliberately NOT the real REQUIRED_DEFAULT_FEATURES/Cargo.toml content, so the self-test proves
# the MECHANISM works and keeps working as the real product decisions (and the real feature list)
# change over time.

SELF_TEST_REQUIRED = {"dev-keys", "openai-notes"}

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


def dry_run_cases() -> list[tuple[str, str, set[str]]]:
    return [
        ("launch OK fixture reports nothing missing", FIXTURE_LAUNCH_OK, set()),
        ("operator OK fixture reports nothing missing", FIXTURE_OPERATOR_OK, set()),
        (
            "AI_FEATURES-dropped fixture reports BOTH features missing",
            FIXTURE_LAUNCH_REGRESSED,
            set(SELF_TEST_REQUIRED),
        ),
        (
            "a dry run with no --features flag at all reports both missing, not vacuously OK",
            FIXTURE_NO_FEATURES_AT_ALL,
            set(SELF_TEST_REQUIRED),
        ),
        (
            "a substring-only feature list (cloud-stt) does not falsely satisfy "
            "dev-keys/openai-notes",
            FIXTURE_SUBSTRING_TRAP,
            set(SELF_TEST_REQUIRED),
        ),
    ]


# --- fixtures for the Cargo.toml tag parser -----------------------------------------------

FIXTURE_TOML_OK = """\
[features]
default = []
# On-device speech-to-text. AUTO-enabled when cmake is present.
#
# LAUNCH_REACHABILITY: AUTO — auto-enabled when cmake is on PATH.
stt = ["dep:selahcue-stt"]
# Developer AI provider keys.
#
# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.
dev-keys = []
# Live cloud endpoint that does not exist yet.
#
# LAUNCH_REACHABILITY: OPT-IN — no endpoint to reach yet.
cloud-live = ["dep:whatever"]

[dependencies]
tauri = "2"
"""

# The 86akby7th regression, reproduced structurally: a feature lands in [features] with a full
# prose comment but NO LAUNCH_REACHABILITY tag at all -- exactly what `cloud-stt` looked like
# before 86akd10dq. Must be a HARD FAILURE, not "assume not required".
FIXTURE_TOML_MISSING_TAG = """\
[features]
default = []
# Cloud (Deepgram) live transcription. Off by default. No tag below -- forgot it.
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_BAD_TAG = """\
[features]
default = []
# Typo'd tag value.
#
# LAUNCH_REACHABILITY: REQUIRED-ISH
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_DUPLICATE_TAG = """\
[features]
default = []
# Two tags in one block -- ambiguous, must fail rather than silently pick one.
#
# LAUNCH_REACHABILITY: REQUIRED
# LAUNCH_REACHABILITY: OPT-IN
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""


def tag_parser_cases() -> list[tuple[str, str, dict[str, str], list[str]]]:
    return [
        (
            "a fully-tagged [features] block derives the right REQUIRED set with no problems",
            FIXTURE_TOML_OK,
            {"stt": "AUTO", "dev-keys": "REQUIRED", "cloud-live": "OPT-IN"},
            [],
        ),
        (
            "a feature with NO tag at all is reported as a problem, not silently untagged",
            FIXTURE_TOML_MISSING_TAG,
            {},
            ["`cloud-stt` has no `LAUNCH_REACHABILITY:` tag in its comment block"],
        ),
        (
            "an unrecognised tag value is reported as a problem",
            FIXTURE_TOML_BAD_TAG,
            {},
            [
                "`cloud-stt`'s `LAUNCH_REACHABILITY:` tag 'REQUIRED-ISH' is not one of "
                "['AUTO', 'OPT-IN', 'REQUIRED']"
            ],
        ),
        (
            "two tags in one comment block is ambiguous and reported as a problem",
            FIXTURE_TOML_DUPLICATE_TAG,
            {},
            [
                "`cloud-stt` has 2 `LAUNCH_REACHABILITY:` tags in its comment block "
                "(ambiguous): ['REQUIRED', 'OPT-IN']"
            ],
        ),
    ]


def self_test() -> int:
    failures = []
    for name, fixture, expected_missing in dry_run_cases():
        actual = missing_features(fixture, SELF_TEST_REQUIRED)
        if actual != expected_missing:
            failures.append(
                f"{name}: expected missing={sorted(expected_missing)}, got={sorted(actual)}"
            )

    for name, fixture, expected_tags, expected_problems in tag_parser_cases():
        tags, problems = parse_feature_tags(fixture)
        if tags != expected_tags or problems != expected_problems:
            failures.append(
                f"{name}: expected tags={expected_tags} problems={expected_problems}, "
                f"got tags={tags} problems={problems}"
            )

    # Mutation control, in the repo's own idiom: take a known-GOOD fixture, delete the tag for
    # one feature (the exact shape of the 86akby7th regression), and confirm the parser flips
    # from zero problems to reporting exactly that feature -- proving the enforcement actually
    # bites rather than only running on fixtures built to already contain a missing tag.
    mutated = FIXTURE_TOML_OK.replace(
        "#\n# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.\ndev-keys = []",
        "dev-keys = []",
    )
    if mutated == FIXTURE_TOML_OK:
        failures.append("mutation control: the string replace did not match FIXTURE_TOML_OK")
    else:
        tags, problems = parse_feature_tags(mutated)
        if "dev-keys" in tags or not any("dev-keys" in p for p in problems):
            failures.append(
                "mutation control: deleting dev-keys' tag did not surface as a problem "
                f"(tags={tags}, problems={problems})"
            )

    total = len(dry_run_cases()) + len(tag_parser_cases()) + 1
    if failures:
        print("check_launch_reachability self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"check_launch_reachability self-test: {total} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    cargo_text = OPERATOR_CARGO_TOML.read_text()
    tags, problems = parse_feature_tags(cargo_text)
    if problems:
        print(
            f"check_launch_reachability: {OPERATOR_CARGO_TOML.relative_to(REPO_ROOT)} has "
            "feature(s) with no valid reachability decision recorded:",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "  Add a `# LAUNCH_REACHABILITY: REQUIRED` / `AUTO` / `OPT-IN` line to the feature's "
            "own comment block (see this script's DERIVATION docstring section for what each "
            "means) before merging -- an off-by-default feature cannot land without recording "
            "whether `make launch`/`make operator` are supposed to reach it.",
            file=sys.stderr,
        )
        return 1

    required = required_from_tags(tags)
    failed = False
    for target in TARGETS:
        dry_run_text = run_make_dry(target)
        missing = missing_features(dry_run_text, required)
        if missing:
            failed = True
            print(
                f"`make {target}` (default invocation) does not reach: "
                f"{', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            print(
                "  These Cargo features are tagged `LAUNCH_REACHABILITY: REQUIRED` in "
                f"{OPERATOR_CARGO_TOML.relative_to(REPO_ROOT)}, meaning they must be reachable "
                "from `make launch`/`make operator` by default. If downgrading one to AUTO/OPT-IN "
                "was intentional, change its tag there and say why in the commit; if not, this is "
                "the exact regression 86akcmzyq/86akd10dq fixed.",
                file=sys.stderr,
            )
    if failed:
        return 1
    print(
        "check_launch_reachability: "
        f"{sorted(required)} (LAUNCH_REACHABILITY: REQUIRED in "
        f"{OPERATOR_CARGO_TOML.relative_to(REPO_ROOT)}) reachable from `make launch`/`make "
        "operator` by default"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
