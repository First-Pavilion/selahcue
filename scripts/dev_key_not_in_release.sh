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
# Each fix narrowed the gap by one spelling. This asks the only question that matters --
# ARE THE KEY BYTES IN THE THING WE SHIP -- and closes every one of those routes at once,
# including the environment, plus any future runtime loader.
#
# It was deferred on the belief that it "needs something to link the crate first". That was
# wrong: `cargo build -p selahcue-licensing --release` emits an rlib today, and the scan takes
# seconds. The earlier guards are kept because they name the specific cause for the ordinary
# cases -- they are not the gate.
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
