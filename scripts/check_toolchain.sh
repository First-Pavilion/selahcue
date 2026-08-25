#!/bin/sh
# Assert the Rust toolchain actually running is exactly the one rust-toolchain.toml pins.
#
# This is the mechanism that makes "`make ci` mirrors CI" a CHECKED property instead of a
# claim in a README. Both the Makefile's `ci` target and every Rust job in
# .github/workflows/ci.yml call this script BEFORE running any gate, so the local gate and
# the pipeline provably use the same compiler.
#
# Without it the two agreed only by coincidence, and when they stopped agreeing nothing said
# so: stable moved 1.97.1 -> 1.98.0 on 2026-08-18, the new lint
# `clippy::chunks_exact_to_as_chunks` met `-D warnings`, and `main` went nine days without a
# green run while `make ci` reported ALL GREEN on the older compiler. ClickUp 86ak5rc9c.
#
# It also checks clippy specifically, not just rustc: clippy is the component that broke, and
# a clippy from a different toolchain is a different gate even when rustc looks right. That
# sub-check is skipped where clippy is not installed at all (CI's launch-smoke job builds and
# runs the app but never lints, so it installs no clippy component) -- skipping there is not a
# hole, because every job that actually RUNS clippy installs it and is therefore checked.
#
# Usage:
#   check_toolchain.sh                  assert the running toolchain matches the pin
#   check_toolchain.sh --print-channel  print the pinned version and exit (no toolchain needed)
#
# --print-channel exists so ci.yml does not re-implement the parsing. It did, once, and the
# copy validated less than this one: it accepted a floating channel that three jobs later
# rejected. One parser, one set of rules.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pin_file="$root/rust-toolchain.toml"

# rustup resolves the toolchain from the CURRENT directory, but the pin is found relative to
# this script. Run the checks from the repository root so the two can never disagree about
# which directory's toolchain is being asserted.
cd "$root"

if [ ! -f "$pin_file" ]; then
    echo "toolchain: $pin_file is missing. The pin IS the gate -- restore it." >&2
    exit 1
fi

# TOML accepts either quote style, and rustup honours both. Parsing only double quotes
# would reject a perfectly legal `channel = '1.98.0'` -- and because this same parser
# feeds the `changes` job that every other job depends on, one quote-style edit would
# fail the whole pipeline with a message about a missing channel. Not a bypass (every
# divergence lands RED), but a false RED from the guard whose entire job is to make the
# signal trustworthy.
pinned=$(sed -n -e 's/^[[:space:]]*channel[[:space:]]*=[[:space:]]*"\([^"]*\)".*$/\1/p' \
                -e "s/^[[:space:]]*channel[[:space:]]*=[[:space:]]*'\([^']*\)'.*\$/\1/p" "$pin_file")
if [ -z "$pinned" ]; then
    echo "toolchain: no [toolchain] channel found in $pin_file" >&2
    exit 1
fi

# A floating channel here would reintroduce the very drift this file prevents, so refuse it
# outright rather than silently gating on "whatever stable is today".
if ! echo "$pinned" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "toolchain: rust-toolchain.toml pins '$pinned', which is not an exact version." >&2
    echo "           Pin an exact x.y.z -- a floating channel cannot be gated on." >&2
    exit 1
fi

if [ "${1:-}" = "--print-channel" ]; then
    echo "$pinned"
    exit 0
fi

# Capture rather than pipe. `rustc --version | awk` reports awk's exit status, so a missing or
# broken rustc would sail through as success -- the same swallowed-exit-code pattern that has
# already produced false greens in this repository twice.
#
# Capture stdout ONLY, and parse by pattern rather than by field position. rustup writes
# progress to stderr, and when rust-toolchain.toml names components the running toolchain does
# not have yet, it installs them on first use and prints "info: syncing channel updates..."
# first. An earlier version of this merged stderr in and took field 2 of the whole blob, so it
# read the version as "syncing" and failed both launch-smoke jobs -- the fix for a swallowed
# exit code introducing a parsing bug of its own.
# `if !` rather than a bare assignment: under `set -e` a failing command substitution in an
# assignment exits the shell immediately with the child's status, so the diagnostic below
# would never print. It failed closed either way, but with a bare "exit 127" and no reason.
if ! rustc_out=$(rustc --version 2>/dev/null); then
    echo "toolchain: could not run rustc. Its output was:" >&2
    rustc --version >&2 2>&1 || true
    exit 1
fi
active=$(printf '%s\n' "$rustc_out" | sed -n 's/^rustc \([0-9][0-9.]*\).*/\1/p' | head -1)
if [ -z "$active" ]; then
    echo "toolchain: could not parse a version out of rustc --version:" >&2
    printf '  %s\n' "$rustc_out" >&2
    exit 1
fi

if [ "$active" != "$pinned" ]; then
    echo "toolchain: MISMATCH -- refusing to gate on a compiler nobody pinned." >&2
    echo "           rust-toolchain.toml pins : $pinned" >&2
    echo "           rustc actually running   : $active" >&2
    echo "" >&2
    echo "           rustup normally honours rust-toolchain.toml automatically. Seeing this" >&2
    echo "           means something overrode it -- a 'rustup override' in this directory, an" >&2
    echo "           explicit 'cargo +toolchain', or RUSTUP_TOOLCHAIN in the environment." >&2
    echo "           Fix the override; do not edit the pin to match your machine." >&2
    exit 1
fi

# clippy reports its own version as 0.1.<rust-minor>; anything else means the clippy on PATH
# came from a different toolchain than the rustc we just verified.
if clippy_out=$(cargo clippy --version 2>/dev/null); then
    # Same pattern-based parse as rustc above, for the same reason.
    clippy_version=$(printf '%s\n' "$clippy_out" | sed -n 's/^clippy \([0-9][0-9.]*\).*/\1/p' | head -1)
    pinned_minor=$(echo "$pinned" | cut -d. -f2)
    clippy_minor=$(echo "$clippy_version" | cut -d. -f3)
    if [ -n "$clippy_version" ] && [ "$clippy_minor" != "$pinned_minor" ]; then
        echo "toolchain: clippy does not belong to the pinned toolchain." >&2
        echo "           expected clippy 0.1.$pinned_minor (for rustc $pinned)" >&2
        echo "           got      $clippy_out" >&2
        exit 1
    fi
    echo "toolchain: rustc $active + clippy $clippy_version (pinned by rust-toolchain.toml)"
else
    echo "toolchain: rustc $active (pinned by rust-toolchain.toml); clippy not installed here, not checked"
fi
