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
by reading each registered crate's own `[features]` table (see MULTI-CRATE SCOPE) and requiring
every feature there (other than `default`) to carry TWO tags in its own comment block -- the same
comment block that already has to explain, in prose, why the feature defaults off:

  `LAUNCH_REACHABILITY: REQUIRED | AUTO | OPT-IN`
    * `REQUIRED` -- a product/owner decision (86akcmzrd is the precedent) that this feature must
      show up in `make launch`/`make operator`'s DEFAULT resolved `--features` list,
      unconditionally (modulo an explicit `AI=0`/`STT=0`/`RELEASE=1` override).
    * `AUTO` -- reachable only when a local probe succeeds (e.g. `stt`: cmake on PATH; `ndi`: the
      SDK is vendored), by design. Not required, because nobody has made the owner call that this
      must work with no toolchain/SDK present.
    * `OPT-IN` -- no dev launch target auto-enables this; reachable only via an explicit
      `OP_FEATURES=`/`cargo build --features` override. Typically because the thing it talks to
      (a live endpoint, say) does not exist yet, so there is nothing for a default `make launch`
      to usefully reach.

  `RELEASE: SAFE | UNSAFE` (86akd10dq remediation -- Sana S-1 / Cody Finding A / Quinn High)
    * `UNSAFE` -- must never reach a `RELEASE=1`/`--release` build of the crate that declares it.
      Cross-checked against the Makefile's own `RELEASE_UNSAFE_FEATURES` registry (see RELEASE
      CROSS-CHECK below) so the two cannot drift apart silently the way the reachability set used
      to before this script existed at all.
    * `SAFE` -- no release-boundary concern (reads no developer-only credential, or ships in a
      real release artefact already, e.g. `stt` in the Windows installer).

A feature with NO tag on either axis, more than one tag on an axis, or an unrecognised tag value,
is a HARD FAILURE of this script -- not a silent "assume not required" / "assume safe". This is
the actual fix, not the relocation: today, a new off-by-default feature can land with no
reachability or release-boundary decision recorded anywhere and nothing objects. After this
change, it cannot -- the gate that already runs on every `make ci` and every CI push refuses to
pass until someone tags it on BOTH axes, which forces the decision to be made (and recorded, in
the one file a reviewer is already looking at for this exact feature) in the SAME PR that adds
the feature, rather than in a follow-up commit to an unrelated script or Makefile line that is
easy to forget entirely.

MULTI-CRATE SCOPE (86akd10dq remediation -- Cody Finding B / Quinn, independently found the same
gap). The first cut of this derivation only ever read `selahcue-operator/Cargo.toml`. But `make
launch` also builds `selahcue-desktop` (`build-output`'s `cargo build ... -p selahcue-desktop
$(DESKTOP_FEATURES)`), which has its own `[features]` table (`encryption`, `ndi`) feeding
`DESKTOP_FEATURES` in the same Makefile -- and nothing ever opened that file, so a future
off-by-default feature there got ZERO enforcement: not a failed check, not even a "missing tag"
error, because the crate was never in scope to begin with. `CRATE_MANIFESTS` below is now every
crate `make launch`/`make operator` build directly with their own `--features` flag, and every
one of them is fully in scope for both tag axes.

`CRATE_MANIFESTS` ITSELF IS NOT DERIVED, and that is an explicit, argued choice rather than an
oversight matching the earlier one: there is no independent, machine-readable source of "which
crate directories make launch/operator build directly" the way Cargo.toml is the source for a
crate's own feature names, or `cargo metadata` is for a workspace's package list -- reading it
back out of the Makefile's own `-p`/`--manifest-path` tokens would mean reading the very artefact
this script exists to check, exactly the circularity the original design rejected for feature
names. The difference that makes a hardcoded registry defensible here and not for feature names:
a new crate entering the dev-launch path is a rare, visible, architectural event (a new Cargo.toml
plus a new Makefile recipe line, both already under heavy review), unlike a new Cargo feature,
which is added routinely, inside one crate, as part of nearly every feature PR. Trusting a
hardcoded list unconditionally would still be the same mistake, though -- so
`assert_no_unregistered_crates` parses every `-p <name>` / `crates/<name>/Cargo.toml` token that
actually appears in a REAL `make -n launch`/`make -n operator` dry run and hard-fails if any name
is not a key in `CRATE_MANIFESTS`, so a third crate joining the dev-launch path without a matching
registry entry is a loud failure, not a silent blind spot. `TARGETS` below gets the same treatment
for the same reason, and stays a bare tuple for a stronger reason: unlike crate names (cargo
metadata) or feature names (Cargo.toml), there is no source of "which Makefile targets are real
dev-launch entry points" OTHER than the Makefile itself, so deriving it would mean reading the one
file this script is independent of -- `run`/`run-release` already reduce to `launch` so they need
no separate entry, and a genuinely new default dev-launch target is exactly the kind of rare,
reviewed, `.PHONY`-list change a human is already looking straight at.

COLLISION GUARD (Quinn's point on `missing_features()`). The dry-run comparison below unions
every `--features <list>` occurrence anywhere in a target's dry-run text into one flat set,
rather than tying a specific required feature to the exact command line that builds ITS crate.
Quinn is right that this could in principle let an unrelated crate's flag satisfy a requirement
by name coincidence -- and worse, `run`/`operator`'s recipe on Darwin shells out to
`scripts/run_operator_macapp.sh --features ...`, which carries no `-p`/`--manifest-path` token
of its own AT ALL in a `make -n` dry run (the manifest path lives inside that script, invisible
to a dry run that never executes it) -- so tying every required feature to an explicit per-line
crate attribution is not reliably possible on the exact platform (macOS) this check is wired into
CI for. Instead: `assert_no_cross_crate_feature_collisions` makes it a hard failure for two
registered crates to declare the same feature name at all. With that invariant held, a feature
name found ANYWHERE in a target's resolved `--features` union is unambiguous evidence about the
one crate that could have produced it, regardless of whether that specific line's crate identity
was parseable -- a guarantee that does not depend on macOS's wrapper-script blind spot, and is
simpler than trying to attribute lines that a dry run cannot always identify.

RELEASE CROSS-CHECK (Sana S-1 / Cody Finding A / Quinn High, the Make-half of the `cloud-stt`
release-boundary remediation). Every feature tagged `RELEASE: UNSAFE` across every registered
crate must appear, as an exact token, in the Makefile's own `RELEASE_UNSAFE_FEATURES := ...`
line -- and every token in that line must correspond to a feature actually tagged `UNSAFE`
somewhere. This is the same shape of guarantee DERIVATION gives the reachability set, applied to
the release boundary: a Makefile edit that silently drops a token from `RELEASE_UNSAFE_FEATURES`,
or a Cargo.toml edit that tags a feature `UNSAFE` without updating the Makefile, now fails this
check instead of drifting apart silently. Scoped to `selahcue-operator` today because
`release-ai-guard` (the actual enforcement mechanism) only ever filters `OP_FEATURES_WORDS`; if a
future feature in another registered crate is ever tagged `UNSAFE`, this check still requires it
to appear in `RELEASE_UNSAFE_FEATURES`, which forces whoever adds it to notice that no Make-level
guard currently reads that list for any crate but the operator, and build one -- rather than
tagging it and believing something enforces it when nothing does.

FEATURE-NAME AUTHORITY (Sana S-2). The line-based comment scanner above cannot see every legal
TOML spelling of a feature key -- an indented key, or a quoted key (`"cloud-stt" = [...]`), both
of which Cargo accepts and both of which would silently exit the tag-enforcement regime with no
diagnostic under a narrower regex. Rather than widen the regex to chase spellings by hand (the
exact hand-maintained-list shape this whole script exists to move away from), the real check
cross-references each crate's tagged feature names against `cargo metadata`'s own authoritative
feature list for that crate's manifest. Any name `cargo metadata` reports that the scanner did
not find a tag for -- regardless of why the scanner missed it -- is a hard failure naming the
feature, not a silent gap. (Not run in `--self-test`: it would require invoking `cargo` against
the real manifests, which the self-test's whole point is to avoid needing.)

HOW THE CHECK WORKS. Runs `make -n <target>` (GNU Make's dry run: prints the resolved recipe
text without executing any of it) for both `launch` and `operator`, with AI/STT/RELEASE/
OP_FEATURES cleared from the environment first so the DEFAULT resolution is what gets checked,
not whatever override happened to be exported in the calling shell (Make's `?=` respects an
inherited environment variable exactly like a command-line override). Every `--features
<comma-list>` occurrence anywhere in that dry-run text is unioned into one set (see COLLISION
GUARD for why that is safe) and every REQUIRED feature must be an exact comma-split TOKEN in that
union, never a substring match: the Makefile's `stt-preflight`/`OP_FEATURES_WORDS` comments name
`cloud-stt` containing "stt" as a substring as exactly the trap a naive `in` check would fall
into.

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

Self-test: `check_launch_reachability.py --self-test` exercises the dry-run comparison, the
Cargo.toml tag parser (both axes), the cross-crate collision guard, the crate-registry drift
check, and the Makefile RELEASE_UNSAFE_FEATURES cross-check -- against fixed fixtures, including
several built by deleting or corrupting a tag from a fixture `[features]` block (the exact
regressions this version closes) -- without touching the real Makefile, the real Cargo.toml
files, or invoking `make`/`cargo` at all, so it runs anywhere. The real check
(`check_launch_reachability.py`, no flag) reads the real Cargo.toml files, the real Makefile, and
shells out to the actual `make -n launch` / `make -n operator` / `cargo metadata` in this repo
checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = REPO_ROOT / "implementation" / "desktop"
MAKEFILE_PATH = REPO_ROOT / "Makefile"

# See MULTI-CRATE SCOPE in the module docstring for what this is, and why it is a hardcoded
# registry rather than something derived, with an automatic drift check against it regardless.
CRATE_MANIFESTS: dict[str, Path] = {
    "selahcue-operator": DESKTOP_ROOT / "crates" / "selahcue-operator" / "Cargo.toml",
    "selahcue-desktop": DESKTOP_ROOT / "crates" / "selahcue-desktop" / "Cargo.toml",
}

# See DERIVATION in the module docstring for what each tag on each axis means.
LAUNCH_TAGS = {"REQUIRED", "AUTO", "OPT-IN"}
RELEASE_TAGS = {"SAFE", "UNSAFE"}

TARGETS = ("launch", "operator")

FEATURES_FLAG = re.compile(r"--features\s+(\S+)")
FEATURE_DEF = re.compile(r"^([A-Za-z0-9_-]+)\s*=")
LAUNCH_TAG_RE = re.compile(r"^#\s*LAUNCH_REACHABILITY:\s*(\S+)")
RELEASE_TAG_RE = re.compile(r"^#\s*RELEASE:\s*(\S+)")
CRATE_NAME_IN_MANIFEST_PATH = re.compile(r"crates/([A-Za-z0-9_-]+)/Cargo\.toml")
CRATE_NAME_VIA_DASH_P = re.compile(r"(?:^|\s)-p\s+([A-Za-z0-9_-]+)")
RELEASE_UNSAFE_LINE = re.compile(r"^RELEASE_UNSAFE_FEATURES\s*:=\s*(.*)$", re.MULTILINE)


class FeatureTags(NamedTuple):
    reachability: str
    release: str


def _validate_axis(
    feature: str, axis: str, found: list[str], valid: set[str], problems: list[str]
) -> str | None:
    """Shared validation for one tag axis on one feature: exactly one occurrence, and it must be
    a recognised value. Appends a human-readable diagnostic to `problems` and returns None for
    anything else -- missing, ambiguous (>1), or unrecognised."""
    if not found:
        problems.append(f"`{feature}` has no `{axis}:` tag in its comment block")
        return None
    if len(found) > 1:
        problems.append(
            f"`{feature}` has {len(found)} `{axis}:` tags in its comment block "
            f"(ambiguous): {found}"
        )
        return None
    if found[0] not in valid:
        problems.append(
            f"`{feature}`'s `{axis}:` tag {found[0]!r} is not one of {sorted(valid)}"
        )
        return None
    return found[0]


def parse_feature_tags(cargo_toml_text: str) -> tuple[dict[str, FeatureTags], list[str]]:
    """Every non-`default` feature declared in the `[features]` table of a Cargo.toml, mapped to
    its `(LAUNCH_REACHABILITY, RELEASE)` tags -- plus a list of human-readable problems for any
    feature missing a tag on either axis, carrying more than one, or carrying an unrecognised
    one. A Cargo.toml with NO `[features]` table at all is not a problem -- it simply has nothing
    to tag (needed now that `CRATE_MANIFESTS` covers more than one crate; a future registered
    crate with no optional features must not be flagged as broken for lacking a section it has
    no reason to have).

    Deliberately line-based rather than a TOML parser: a TOML parser would discard the very
    comments this function exists to read. The contract this depends on: each tag line sits
    somewhere in the CONTIGUOUS block of `#`-prefixed lines immediately above the feature's own
    `name = [...]` line, with nothing but comment lines between them. See FEATURE-NAME AUTHORITY
    in the module docstring for the spellings this cannot see, and how the real check catches
    them anyway via `cargo metadata`.
    """
    lines = cargo_toml_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "[features]")
    except StopIteration:
        return {}, []

    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s != "[features]":
            end = i
            break

    tags: dict[str, FeatureTags] = {}
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
                block.reverse()
                launch_found = [tm.group(1) for l in block if (tm := LAUNCH_TAG_RE.match(l))]
                release_found = [tm.group(1) for l in block if (tm := RELEASE_TAG_RE.match(l))]
                launch_tag = _validate_axis(
                    name, "LAUNCH_REACHABILITY", launch_found, LAUNCH_TAGS, problems
                )
                release_tag = _validate_axis(
                    name, "RELEASE", release_found, RELEASE_TAGS, problems
                )
                if launch_tag is not None and release_tag is not None:
                    tags[name] = FeatureTags(launch_tag, release_tag)
        i += 1
    return tags, problems


def collect_all_tags() -> tuple[dict[str, FeatureTags], dict[str, dict[str, FeatureTags]], list[str]]:
    """Parse every registered crate's Cargo.toml. Returns `(merged, per_crate, problems)`:
    `merged` is every feature name -> tags, valid only because of the collision check below (see
    COLLISION GUARD in the module docstring); `per_crate` keeps each crate's own tags separately,
    needed by the `cargo metadata` cross-check, which must compare like-for-like against one
    manifest at a time.
    """
    merged: dict[str, FeatureTags] = {}
    owner: dict[str, str] = {}
    per_crate: dict[str, dict[str, FeatureTags]] = {}
    problems: list[str] = []
    for crate_name, manifest_path in CRATE_MANIFESTS.items():
        crate_tags, crate_problems = parse_feature_tags(manifest_path.read_text())
        per_crate[crate_name] = crate_tags
        rel = manifest_path.relative_to(REPO_ROOT)
        problems.extend(f"{crate_name} ({rel}): {p}" for p in crate_problems)
        for feature_name, feature_tags in crate_tags.items():
            if feature_name in owner:
                problems.append(
                    f"feature name `{feature_name}` is declared by BOTH `{owner[feature_name]}` "
                    f"and `{crate_name}` -- this script unions every crate's --features tokens "
                    "from the dry run without attributing a line to a specific crate (see "
                    "COLLISION GUARD in the module docstring), so two crates sharing a feature "
                    "name would let one crate's flag silently satisfy the other's requirement. "
                    "Rename one of them."
                )
                continue
            merged[feature_name] = feature_tags
            owner[feature_name] = crate_name
    return merged, per_crate, problems


def required_from_tags(tags: dict[str, FeatureTags]) -> set[str]:
    """Features tagged `LAUNCH_REACHABILITY: REQUIRED` -- the set this script asserts is
    reachable from `make launch`/`make operator` by default."""
    return {name for name, t in tags.items() if t.reachability == "REQUIRED"}


def release_unsafe_from_tags(tags: dict[str, FeatureTags]) -> set[str]:
    """Features tagged `RELEASE: UNSAFE` -- the set that must never reach a RELEASE=1/--release
    build, cross-checked against the Makefile's own `RELEASE_UNSAFE_FEATURES` registry."""
    return {name for name, t in tags.items() if t.release == "UNSAFE"}


def resolved_features(dry_run_text: str) -> set[str]:
    """Every feature token named in any `--features <list>` occurrence in `dry_run_text`. See
    COLLISION GUARD in the module docstring for why a flat union (rather than per-line crate
    attribution) is a safe comparison, given the cross-crate collision check this script also
    runs."""
    features: set[str] = set()
    for match in FEATURES_FLAG.finditer(dry_run_text):
        features.update(match.group(1).split(","))
    return features


def missing_features(dry_run_text: str, required: set[str]) -> set[str]:
    """The `required` features that do NOT appear as a token anywhere in `dry_run_text`."""
    return required - resolved_features(dry_run_text)


def crate_mentions(dry_run_text: str) -> set[str]:
    """Every crate name a dry run's text names explicitly, via either `-p <name>` or a
    `--manifest-path .../crates/<name>/Cargo.toml`. Used to catch a crate joining the dev-launch
    path without a matching `CRATE_MANIFESTS` entry -- see MULTI-CRATE SCOPE."""
    return set(CRATE_NAME_IN_MANIFEST_PATH.findall(dry_run_text)) | set(
        CRATE_NAME_VIA_DASH_P.findall(dry_run_text)
    )


def unregistered_crate_mentions(dry_run_texts: list[str]) -> set[str]:
    """Crate names mentioned across every given dry run that are NOT a key in `CRATE_MANIFESTS`."""
    mentioned: set[str] = set()
    for text in dry_run_texts:
        mentioned |= crate_mentions(text)
    return mentioned - set(CRATE_MANIFESTS)


def parse_release_unsafe_line(makefile_text: str) -> set[str] | None:
    """The token set of the Makefile's `RELEASE_UNSAFE_FEATURES := ...` line, or `None` if that
    line cannot be found at all (a hard failure at the call site -- the cross-check has nothing
    to compare against)."""
    m = RELEASE_UNSAFE_LINE.search(makefile_text)
    if not m:
        return None
    return set(m.group(1).split())


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


def metadata_feature_names(manifest_path: Path) -> set[str]:
    """The authoritative feature-name set `cargo metadata` reports for the package at
    `manifest_path`, excluding `default`. See FEATURE-NAME AUTHORITY in the module docstring."""
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--no-deps",
            "--format-version",
            "1",
            "--manifest-path",
            str(manifest_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"`cargo metadata` for {manifest_path} failed (exit {result.returncode}):",
            file=sys.stderr,
        )
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SystemExit(1)
    data = json.loads(result.stdout)
    target = manifest_path.resolve()
    for pkg in data.get("packages", []):
        if Path(pkg["manifest_path"]).resolve() == target:
            return set(pkg.get("features", {}).keys()) - {"default"}
    raise SystemExit(f"cargo metadata reported no package for manifest {manifest_path}")


# --- fixtures for --self-test, modelled on real `make -n launch`/`make -n operator` output ----
# Deliberately NOT the real feature lists/Makefile content, so the self-test proves the MECHANISM
# works and keeps working as the real product decisions (and the real feature lists) change.

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
FIXTURE_LAUNCH_REGRESSED = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt \n"
)
FIXTURE_NO_FEATURES_AT_ALL = "cargo build --manifest-path .../Cargo.toml \n"
FIXTURE_SUBSTRING_TRAP = "cargo build --manifest-path .../Cargo.toml --features cloud-stt,ndi \n"
# A dry run naming both registered crates by their real identifying tokens -- the shape
# `assert_no_unregistered_crates` must accept without complaint.
FIXTURE_BOTH_CRATES_REGISTERED = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml "
    "--features stt,dev-keys,openai-notes,cloud-stt \n"
    "cargo build --manifest-path implementation/desktop/Cargo.toml -p selahcue-desktop "
    "--features ndi \n"
)
# A THIRD crate (`selahcue-widget`, invented) appearing in a dry run with no matching
# CRATE_MANIFESTS entry -- the exact shape of a fourth instance of the reachability-gap class,
# reproduced structurally without needing a real fourth crate to exist.
FIXTURE_UNREGISTERED_CRATE = (
    "cargo build --manifest-path implementation/desktop/crates/selahcue-widget/Cargo.toml "
    "--features some-new-feature \n"
)


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


def crate_registry_cases() -> list[tuple[str, list[str], set[str]]]:
    return [
        (
            "both registered crates' identifying tokens are accepted with no unregistered names",
            [FIXTURE_BOTH_CRATES_REGISTERED],
            set(),
        ),
        (
            "a crate with no CRATE_MANIFESTS entry is reported, not silently ignored",
            [FIXTURE_UNREGISTERED_CRATE],
            {"selahcue-widget"},
        ),
    ]


# --- fixtures for the Cargo.toml tag parser -----------------------------------------------

FIXTURE_TOML_OK = """\
[features]
default = []
# On-device speech-to-text. AUTO-enabled when cmake is present.
#
# LAUNCH_REACHABILITY: AUTO — auto-enabled when cmake is on PATH.
# RELEASE: SAFE — no developer credential involved.
stt = ["dep:selahcue-stt"]
# Developer AI provider keys.
#
# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.
# RELEASE: UNSAFE — must never reach a release build.
dev-keys = []
# Live cloud endpoint that does not exist yet.
#
# LAUNCH_REACHABILITY: OPT-IN — no endpoint to reach yet.
# RELEASE: SAFE — no developer credential involved.
cloud-live = ["dep:whatever"]

[dependencies]
tauri = "2"
"""

# The 86akby7th regression, reproduced structurally: a feature lands in [features] with a full
# prose comment but NO tags at all -- exactly what `cloud-stt` looked like before 86akd10dq.
FIXTURE_TOML_MISSING_TAGS = """\
[features]
default = []
# Cloud (Deepgram) live transcription. Off by default. No tags below -- forgot them.
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_BAD_TAG = """\
[features]
default = []
# Typo'd tag value.
#
# LAUNCH_REACHABILITY: REQUIRED-ISH
# RELEASE: SAFE
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

FIXTURE_TOML_DUPLICATE_TAG = """\
[features]
default = []
# Two LAUNCH_REACHABILITY tags in one block -- ambiguous, must fail rather than silently pick one.
#
# LAUNCH_REACHABILITY: REQUIRED
# LAUNCH_REACHABILITY: OPT-IN
# RELEASE: SAFE
cloud-stt = ["stt", "selahcue-stt-cloud/deepgram"]
"""

# A Cargo.toml with no [features] table at all -- a legitimate shape for a future registered
# crate with no optional features, and must NOT be reported as a problem.
FIXTURE_TOML_NO_FEATURES_TABLE = """\
[package]
name = "some-crate"

[dependencies]
serde = "1"
"""


def tag_parser_cases() -> list[tuple[str, str, dict[str, FeatureTags], list[str]]]:
    return [
        (
            "a fully-tagged [features] block derives the right tags with no problems",
            FIXTURE_TOML_OK,
            {
                "stt": FeatureTags("AUTO", "SAFE"),
                "dev-keys": FeatureTags("REQUIRED", "UNSAFE"),
                "cloud-live": FeatureTags("OPT-IN", "SAFE"),
            },
            [],
        ),
        (
            "a feature with NO tags at all is reported as a problem on both axes",
            FIXTURE_TOML_MISSING_TAGS,
            {},
            [
                "`cloud-stt` has no `LAUNCH_REACHABILITY:` tag in its comment block",
                "`cloud-stt` has no `RELEASE:` tag in its comment block",
            ],
        ),
        (
            "an unrecognised LAUNCH_REACHABILITY tag value is reported as a problem",
            FIXTURE_TOML_BAD_TAG,
            {},
            [
                "`cloud-stt`'s `LAUNCH_REACHABILITY:` tag 'REQUIRED-ISH' is not one of "
                "['AUTO', 'OPT-IN', 'REQUIRED']"
            ],
        ),
        (
            "two LAUNCH_REACHABILITY tags in one comment block is ambiguous and reported",
            FIXTURE_TOML_DUPLICATE_TAG,
            {},
            [
                "`cloud-stt` has 2 `LAUNCH_REACHABILITY:` tags in its comment block "
                "(ambiguous): ['REQUIRED', 'OPT-IN']"
            ],
        ),
        (
            "a Cargo.toml with no [features] table at all is not a problem",
            FIXTURE_TOML_NO_FEATURES_TABLE,
            {},
            [],
        ),
    ]


# --- fixtures for the cross-crate collision guard -------------------------------------------

FIXTURE_TOML_COLLIDING_A = """\
[features]
default = []
# Crate A's own take on a feature literally named `shared-name`.
#
# LAUNCH_REACHABILITY: REQUIRED — crate A's reason.
# RELEASE: SAFE
shared-name = []
"""

FIXTURE_TOML_COLLIDING_B = """\
[features]
default = []
# Crate B independently picked the SAME feature name -- a collision this script must refuse to
# resolve silently (see COLLISION GUARD).
#
# LAUNCH_REACHABILITY: OPT-IN — crate B's reason.
# RELEASE: SAFE
shared-name = []
"""


# --- fixtures for the RELEASE_UNSAFE_FEATURES Makefile cross-check ---------------------------

FIXTURE_MAKEFILE_OK = (
    "RELEASE ?= 0\n"
    "RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt\n"
    "STT ?= auto\n"
)
FIXTURE_MAKEFILE_NO_LINE = "RELEASE ?= 0\nSTT ?= auto\n"


def self_test() -> int:
    failures = []

    for name, fixture, expected_missing in dry_run_cases():
        actual = missing_features(fixture, SELF_TEST_REQUIRED)
        if actual != expected_missing:
            failures.append(
                f"{name}: expected missing={sorted(expected_missing)}, got={sorted(actual)}"
            )

    for name, texts, expected_unregistered in crate_registry_cases():
        actual = unregistered_crate_mentions(texts)
        if actual != expected_unregistered:
            failures.append(
                f"{name}: expected unregistered={sorted(expected_unregistered)}, "
                f"got={sorted(actual)}"
            )

    for name, fixture, expected_tags, expected_problems in tag_parser_cases():
        tags, problems = parse_feature_tags(fixture)
        if tags != expected_tags or problems != expected_problems:
            failures.append(
                f"{name}: expected tags={expected_tags} problems={expected_problems}, "
                f"got tags={tags} problems={problems}"
            )

    # The collision guard, exercised via two crates' worth of tags merged the same way
    # collect_all_tags() does, without needing real files on disk.
    tags_a, problems_a = parse_feature_tags(FIXTURE_TOML_COLLIDING_A)
    tags_b, problems_b = parse_feature_tags(FIXTURE_TOML_COLLIDING_B)
    if problems_a or problems_b:
        failures.append(
            f"collision fixtures should each parse cleanly on their own: {problems_a + problems_b}"
        )
    merged: dict[str, FeatureTags] = {}
    owner: dict[str, str] = {}
    collision_problems: list[str] = []
    for crate_name, crate_tags in (("crate-a", tags_a), ("crate-b", tags_b)):
        for feature_name in crate_tags:
            if feature_name in owner:
                collision_problems.append(feature_name)
                continue
            merged[feature_name] = crate_tags[feature_name]
            owner[feature_name] = crate_name
    if collision_problems != ["shared-name"]:
        failures.append(
            "collision guard: two crates declaring the same feature name was not caught "
            f"(got {collision_problems})"
        )

    # The RELEASE_UNSAFE_FEATURES Makefile cross-check, against fixture Makefile text.
    tokens = parse_release_unsafe_line(FIXTURE_MAKEFILE_OK)
    if tokens != {"dev-keys", "openai-notes", "cloud-stt"}:
        failures.append(f"RELEASE_UNSAFE_FEATURES parse: expected the three tokens, got {tokens}")
    if parse_release_unsafe_line(FIXTURE_MAKEFILE_NO_LINE) is not None:
        failures.append(
            "RELEASE_UNSAFE_FEATURES parse: a Makefile with no such line must report None, "
            "not an empty set (a missing line is a hard failure at the call site, not 'nothing "
            "is unsafe')"
        )

    # Mutation control, in the repo's own idiom: take a known-GOOD fixture, delete ONE feature's
    # tags (the exact shape of the 86akby7th regression), and confirm the parser flips from zero
    # problems to reporting exactly that feature on both axes -- proving the enforcement actually
    # bites rather than only running on fixtures built to already contain a missing tag.
    mutated = FIXTURE_TOML_OK.replace(
        "#\n# LAUNCH_REACHABILITY: REQUIRED — 86akcmzrd.\n"
        "# RELEASE: UNSAFE — must never reach a release build.\n"
        "dev-keys = []",
        "dev-keys = []",
    )
    if mutated == FIXTURE_TOML_OK:
        failures.append("mutation control: the string replace did not match FIXTURE_TOML_OK")
    else:
        tags, problems = parse_feature_tags(mutated)
        if "dev-keys" in tags or not any("dev-keys" in p for p in problems):
            failures.append(
                "mutation control: deleting dev-keys' tags did not surface as a problem "
                f"(tags={tags}, problems={problems})"
            )

    total = (
        len(dry_run_cases())
        + len(crate_registry_cases())
        + len(tag_parser_cases())
        + 1  # collision guard
        + 2  # RELEASE_UNSAFE_FEATURES parse (present + absent)
        + 1  # mutation control
    )
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

    merged_tags, per_crate_tags, problems = collect_all_tags()

    # FEATURE-NAME AUTHORITY (Sana S-2): cross-check the comment scanner's findings for each
    # crate against cargo metadata's own authoritative feature list for that crate.
    for crate_name, manifest_path in CRATE_MANIFESTS.items():
        authoritative = metadata_feature_names(manifest_path)
        scanned = set(per_crate_tags[crate_name])
        unscanned = authoritative - scanned
        for feature_name in sorted(unscanned):
            problems.append(
                f"{crate_name}: cargo metadata reports feature `{feature_name}` that the "
                "comment-tag scanner did not find a tag for -- possibly an unusual TOML "
                "spelling (an indented key, or a quoted key) the line-based scanner cannot see. "
                "Add a `LAUNCH_REACHABILITY:`/`RELEASE:` tag directly above it, using the plain "
                "`name = [...]` spelling if possible."
            )
        stale = scanned - authoritative
        for feature_name in sorted(stale):
            problems.append(
                f"{crate_name}: a `LAUNCH_REACHABILITY:`/`RELEASE:` tag was found for "
                f"`{feature_name}`, but cargo metadata does not know this feature -- it may have "
                "been removed, renamed, or the comment scanner mis-parsed something as a feature "
                "definition."
            )

    if problems:
        print(
            "check_launch_reachability: feature(s) with no valid reachability/release decision "
            "recorded:",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(
            "  Add a `# LAUNCH_REACHABILITY: REQUIRED|AUTO|OPT-IN` AND a `# RELEASE: SAFE|UNSAFE` "
            "line to the feature's own comment block (see this script's DERIVATION docstring "
            "section for what each means) before merging -- an off-by-default feature cannot "
            "land without recording both decisions.",
            file=sys.stderr,
        )
        return 1

    required = required_from_tags(merged_tags)
    release_unsafe = release_unsafe_from_tags(merged_tags)

    dry_run_texts: dict[str, str] = {target: run_make_dry(target) for target in TARGETS}

    unregistered = unregistered_crate_mentions(list(dry_run_texts.values()))
    if unregistered:
        print(
            "check_launch_reachability: `make -n launch`/`make -n operator` reference crate(s) "
            f"not in CRATE_MANIFESTS: {sorted(unregistered)}",
            file=sys.stderr,
        )
        print(
            "  A crate joined the dev-launch path with no matching entry in this script's "
            "CRATE_MANIFESTS registry -- its [features] table (if any) gets zero enforcement. "
            "Add it. See MULTI-CRATE SCOPE in this script's docstring.",
            file=sys.stderr,
        )
        return 1

    makefile_release_unsafe = parse_release_unsafe_line(MAKEFILE_PATH.read_text())
    if makefile_release_unsafe is None:
        print(
            "check_launch_reachability: could not find a `RELEASE_UNSAFE_FEATURES := ...` line "
            f"in {MAKEFILE_PATH.relative_to(REPO_ROOT)} -- the RELEASE cross-check has nothing "
            "to compare against. See RELEASE CROSS-CHECK in this script's docstring.",
            file=sys.stderr,
        )
        return 1
    if makefile_release_unsafe != release_unsafe:
        only_in_makefile = makefile_release_unsafe - release_unsafe
        only_in_tags = release_unsafe - makefile_release_unsafe
        print(
            "check_launch_reachability: the Makefile's RELEASE_UNSAFE_FEATURES and the "
            "Cargo.toml `RELEASE: UNSAFE` tags have drifted apart:",
            file=sys.stderr,
        )
        if only_in_makefile:
            print(
                f"  In the Makefile but not tagged UNSAFE anywhere: {sorted(only_in_makefile)}",
                file=sys.stderr,
            )
        if only_in_tags:
            print(
                f"  Tagged UNSAFE but missing from the Makefile: {sorted(only_in_tags)}",
                file=sys.stderr,
            )
        print(
            "  See RELEASE CROSS-CHECK in this script's docstring -- update whichever side is "
            "stale and say why in the commit.",
            file=sys.stderr,
        )
        return 1

    failed = False
    for target, dry_run_text in dry_run_texts.items():
        missing = missing_features(dry_run_text, required)
        if missing:
            failed = True
            print(
                f"`make {target}` (default invocation) does not reach: "
                f"{', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            print(
                "  These Cargo features are tagged `LAUNCH_REACHABILITY: REQUIRED`, meaning "
                "they must be reachable from `make launch`/`make operator` by default. If "
                "downgrading one to AUTO/OPT-IN was intentional, change its tag and say why in "
                "the commit; if not, this is the exact regression 86akcmzyq/86akd10dq fixed.",
                file=sys.stderr,
            )
    if failed:
        return 1
    print(
        "check_launch_reachability: "
        f"{sorted(required)} reachable from `make launch`/`make operator` by default; "
        f"{sorted(release_unsafe)} confirmed release-unsafe and matched against the Makefile"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
