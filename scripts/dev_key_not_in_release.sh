#!/bin/sh
# THE gate on the development entitlement key. Effect-level, not name-level.
#
# `selahcue-licensing` trusts a development signing key under `#[cfg(debug_assertions)]`, and
# that key's seed is COMMITTED (dev-signing-key.NOT-A-SECRET). A release artefact carrying it
# lets anyone mint unlimited entitlement.
#
# WHY THIS EXISTS RATHER THAN YET MORE GUARDS
# Every earlier control asked a question ABOUT the source or the configuration, and each was
# defeated by a spelling nobody had enumerated:
#
#   * the source guard reads gate TEXT -> defeated by leaving the gate in a comment.
#   * `cargo test --release` asks `cfg!(debug_assertions)` -> defeated by turning that very
#     cfg back on, which is the question it is asking.
#   * the profile scan in import_guards.sh matches `[profile.release]` line headers ->
#     defeated by `[profile]` with an inline `release = { debug-assertions = true }` table,
#     by the legacy `.cargo/config` filename, by a valueless `-C debug-assertions` rustflag,
#     and by a config in a parent directory or $CARGO_HOME.
#   * none of them can see RUSTFLAGS in the environment at all.
#
# Each fix narrowed the gap by one spelling. This asks a different question -- ARE THE KEY
# BYTES IN THE THING WE SHIP -- and closes every one of those CONFIGURATION routes at once,
# including RUSTFLAGS in the environment, which nothing in-repo can see.
#
# WHAT IT DOES NOT CLOSE, stated here because this comment used to claim it closed "any future
# runtime loader" and it does not. The scan is a literal byte-substring search of the emitted
# rlib (dev_key_scan.py, `key in p.read_bytes()`). So it answers exactly one question:
#
#     "is the dev key COMPILED INTO the release artefact?"
#
# It cannot answer "does a release binary OBTAIN the key at runtime". A loader that DERIVES
# the 32 bytes rather than embedding them -- parsing them from the decimal form the seed file
# itself publishes, say -- puts no literal key anywhere in the artefact, and this scan prints
# OK. QA demonstrated exactly that, with the env read placed in the path dependency
# selahcue-cloud so the source guard is blind to it as well.
#
# THE RELEASE `iff` TEST IS THE OTHER HALF, NOT A LESSER COPY OF THIS ONE. An earlier revision
# of these comments called that test "not the gate", which invites deleting it. Do not: the
# two controls are COMPLEMENTARY and neither subsumes the other.
#
#   route                                          | this byte scan | release iff test
#   -----------------------------------------------+----------------+------------------
#   profile table / cargo config / RUSTFLAGS       | KILL           | miss
#   runtime loader, non-literal key                | miss           | KILL
#   ...the same loader behind a runtime trigger    | miss           | miss
#
# The bottom row is QA's demonstrated bypass and is closed by NEITHER control. That is
# accepted deliberately rather than chased with a sixth guard: "no config loader in this
# crate" is a REVIEW-enforced rule (see `TrustedKeys::insert`), and writing one is a
# deliberate act, not an accident a scan would catch.
#
# This scan was deferred once on the belief that it "needs something to link the crate first".
# That was wrong: `cargo build -p selahcue-licensing --release` emits an rlib today, and the
# scan takes seconds. The source-text guards are kept because they name the specific cause for
# the ordinary cases.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DESKTOP="$ROOT/implementation/desktop"
CARGO=${CARGO:-cargo}
TRUST_RS="$DESKTOP/crates/selahcue-licensing/src/trust.rs"
WORK=${TMPDIR:-/tmp}

[ -f "$TRUST_RS" ] || {
  echo "DEV KEY SCAN FAILED: cannot find $TRUST_RS -- repoint this scan, never drop it" >&2
  exit 1
}

echo ">> building selahcue-licensing in both profiles for the dev-key byte scan"
"$CARGO" build --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-licensing --release \
  --message-format=json > "$WORK/sc_release_artifacts.json"
"$CARGO" build --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-licensing \
  --message-format=json > "$WORK/sc_debug_artifacts.json"

python3 "$ROOT/scripts/dev_key_scan.py" \
  "$TRUST_RS" "$WORK/sc_release_artifacts.json" "$WORK/sc_debug_artifacts.json"
