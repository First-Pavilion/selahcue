#!/bin/sh
# Run `cargo audit` (RustSec) against EVERY Cargo root in this repository and fail if any of them
# carries a vulnerability. This is the local twin of the `dependency audit (RustSec)` job in
# .github/workflows/ci.yml, which runs plain `cargo audit` in each of the three roots.
#
# Why it exists (17tnw2b9ax3): hosted CI was billing-blocked, so that job never ran, and `main`
# sat with 12, 12 and 6 compiled-in RustSec vulnerabilities in the three roots until a dependency
# review happened to run `cargo audit` by hand. A check that only exists in a CI job is invisible
# whenever CI is down. `make audit` puts the same check one command away on any developer machine.
#
# The set of roots is DERIVED, not listed: every `Cargo.lock` that git tracks (plus untracked,
# not-ignored ones, so a lockfile that has not been committed yet still counts). This is the same
# source of truth `scripts/check_dependency_audit_coverage.py` uses for CI, for the same reason:
# a hand-maintained list of crate roots is the bug class that hid selahcue-stt (86akmdkdn). A
# fourth root added later is audited here with no edit to this file.
#
# Behaviour, deliberately:
#   * It runs EVERY root even after one fails, then reports all of them. Stopping at the first
#     failure would hide the other roots' state, which is what the "first failing line" masking
#     note on `make ci` warns about.
#   * It exits non-zero if any root fails, if cargo-audit is not installed, if no root is found,
#     or if cargo-audit itself errors (for example the advisory database cannot be fetched). It
#     fails CLOSED: "could not check" is never reported as "clean".
#   * Like CI, only vulnerabilities fail it. `cargo audit` prints unmaintained, unsound and yanked
#     crates as warnings and exits 0 for them; they stay visible in the output.
#   * It needs the network the first time and whenever the advisory database is stale, because
#     cargo-audit fetches the RustSec advisory-db. That is why it is NOT a step of `make ci`
#     (see the comment on the `audit` target in the Makefile).
#
# Usage:
#   sh scripts/cargo_audit_all.sh            # audit this checkout
#   sh scripts/cargo_audit_all.sh <repo>     # audit another git checkout (used by the negative control)
#   CARGO=/path/to/cargo sh scripts/cargo_audit_all.sh
#
# Exit codes: 0 every root clean, 1 at least one root failed, 2 cannot run (tool missing, no roots).

set -u

CARGO="${CARGO:-cargo}"
if [ "$#" -ge 1 ]; then
  ROOT=$(cd "$1" && pwd) || exit 2
else
  ROOT=$(cd "$(dirname "$0")/.." && pwd) || exit 2
fi

if ! "$CARGO" audit --version >/dev/null 2>&1; then
  echo "ERROR: 'cargo audit' is not available (CARGO=$CARGO)." >&2
  echo "  Install it once with:  cargo install cargo-audit --locked" >&2
  echo "  CI installs the same tool with taiki-e/install-action (tool: cargo-audit)." >&2
  exit 2
fi

locks=$(git -C "$ROOT" ls-files --cached --others --exclude-standard -- '*Cargo.lock') || {
  echo "ERROR: could not list Cargo.lock files with git in $ROOT" >&2
  exit 2
}
if [ -z "$locks" ]; then
  echo "ERROR: no Cargo.lock found under $ROOT -- refusing to report 'clean' for zero roots." >&2
  exit 2
fi

failed=0
summary=""
while IFS= read -r lock; do
  [ -n "$lock" ] || continue
  dir=$(dirname "$lock")
  echo ">> cargo audit in $dir"
  if (cd "$ROOT/$dir" && "$CARGO" audit); then
    summary="$summary
  PASS  $dir"
  else
    status=$?
    summary="$summary
  FAIL  $dir (cargo audit exit $status)"
    failed=$((failed + 1))
  fi
done <<EOF
$locks
EOF

echo
echo "cargo audit summary:$summary"
if [ "$failed" -ne 0 ]; then
  echo "FAILED: $failed Cargo root(s) did not pass cargo audit." >&2
  exit 1
fi
echo "OK: every Cargo root passed cargo audit (warnings, if any, are printed above and do not fail)."
