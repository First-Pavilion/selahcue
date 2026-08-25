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
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pin_file="$root/rust-toolchain.toml"

if [ ! -f "$pin_file" ]; then
    echo "toolchain: $pin_file is missing. The pin IS the gate -- restore it." >&2
    exit 1
fi

pinned=$(sed -n 's/^[[:space:]]*channel[[:space:]]*=[[:space:]]*"\([^"]*\)".*$/\1/p' "$pin_file")
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

active=$(rustc --version | awk '{print $2}')
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
if clippy_version=$(cargo clippy --version 2>/dev/null); then
    pinned_minor=$(echo "$pinned" | cut -d. -f2)
    clippy_minor=$(echo "$clippy_version" | awk '{print $2}' | cut -d. -f3)
    if [ "$clippy_minor" != "$pinned_minor" ]; then
        echo "toolchain: clippy does not belong to the pinned toolchain." >&2
        echo "           expected clippy 0.1.$pinned_minor (for rustc $pinned)" >&2
        echo "           got      $clippy_version" >&2
        exit 1
    fi
    echo "toolchain: rustc $active + $clippy_version (pinned by rust-toolchain.toml)"
else
    echo "toolchain: rustc $active (pinned by rust-toolchain.toml); clippy not installed here, not checked"
fi
