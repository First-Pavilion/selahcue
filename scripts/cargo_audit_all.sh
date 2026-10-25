#!/bin/sh
# Run `cargo audit` (RustSec) against EVERY Cargo root in this repository and fail if any of them
# carries a vulnerability. This is the local twin of the `dependency audit (RustSec)` job in
# .github/workflows/ci.yml, which runs plain `cargo audit` in each root.
#
# Why it exists (17tnw2b9ax3): hosted CI was billing-blocked, so that job never ran, and `main`
# sat with 12, 12 and 6 RustSec vulnerabilities in the three roots until a dependency review
# happened to run `cargo audit` by hand. A check that only exists in a CI job is invisible whenever
# CI is down. `make audit` puts the same check one command away on any developer machine.
#
# WHICH ROOTS. Every file named exactly `Cargo.lock` that git lists (tracked, plus untracked but
# not ignored, so a lockfile that has not been committed yet still counts), at any depth. The list
# is derived, not written down, so a further root is audited with no edit to this file. What this
# shares with scripts/check_dependency_audit_coverage.py is the way of listing files (`git ls-files
# --cached --others --exclude-standard`) and the refusal to run when `.gitmodules` exists; that
# script's extra [workspace]-table scan is not repeated here. The two answer different questions:
# that script checks that CI's hand-written audit steps cover every lock, this one audits every lock
# git knows about whether or not CI has a step for it.
#
# IT MUST NOT SAY "PASS" WHEN IT HAS NOT CHECKED. Each of these exits 2 ("cannot run") before any
# root is audited, never 0:
#   * `cargo audit` is not available, or CARGO is not a single executable path;
#   * `cargo audit --version`, run in a root, does not identify itself as cargo-audit, or cargo
#     says on stderr that an alias is shadowing the external subcommand. A `[alias] audit =
#     "version"` in any .cargo/config.toml makes `cargo audit` run something else entirely and
#     exit 0, which would print PASS for an unchecked root;
#   * an `audit.toml` exists in ${CARGO_HOME:-$HOME/.cargo}, in <repo>/.cargo or in <root>/.cargo,
#     because it can silently ignore advisories, so a local PASS could disagree with CI;
#   * CARGO_HOME is set but is not an absolute path, or (CARGO_HOME empty) HOME is not set to an
#     absolute path. cargo-audit resolves a relative CARGO_HOME against the lock directory and an
#     unset HOME through the password database, while this script would look somewhere else, so it
#     could miss an audit.toml that cargo-audit then obeys;
#   * no Cargo.lock is found, `.gitmodules` exists (git cannot list a submodule's files), a lock's
#     path contains a newline, or a lock git lists is missing from the working tree (cargo-audit
#     would generate a fresh lock there and audit that instead).
#
# Behaviour once it is running:
#   * It runs EVERY root even after one fails, then reports all of them. Stopping at the first
#     failure would hide the other roots' state, which is what the "first failing line" masking
#     note on `make ci` warns about.
#   * It exits 1 if any root did not pass. `cargo audit` exits non-zero both for a found
#     vulnerability and for an error such as an advisory-database fetch failure; this script does
#     not tell them apart, so FAIL means "vulnerable, or could not be checked": read the output
#     above the summary.
#   * Like CI, only vulnerabilities fail a root. Unmaintained, unsound and yanked crates are
#     printed as warnings and `cargo audit` exits 0 for them.
#   * cargo-audit fetches the RustSec advisory database on EVERY run (this script never passes
#     --no-fetch), so it needs the network each time; offline, every root FAILs. `make ci` runs it
#     as its last gate, so `make ci` needs the network too; `AUDIT=skip make ci` is the loud,
#     documented opt-out (see the comments on the `audit` target and the end of the `ci` recipe in
#     the Makefile). This script has no opt-out of its own.
#
# Usage:
#   sh scripts/cargo_audit_all.sh            # audit this checkout
#   sh scripts/cargo_audit_all.sh <repo>     # audit another git checkout (used by the self-test)
#   CARGO=/path/to/cargo sh scripts/cargo_audit_all.sh
#
# CARGO must be ONE executable path (a binary or a wrapper script), not a command line:
# `CARGO="cargo +1.98.0"` does not work because the value is run as a single word. Put a wrapper
# script on the path for a toolchain override.
#
# Tested offline by scripts/check_cargo_audit_all.py --self-test (wired into `make ci` and CI).
#
# Signals: SIGINT, SIGTERM and SIGHUP stop the script (exit 130, 143, 129) and remove its temporary
# file. A shell defers a trap until the foreground command finishes, so the exit follows the root
# being audited at that moment, not the remaining ones.
#
# Exit codes: 0 every root passed, 1 at least one root did not pass, 2 cannot run (see above),
# 129/130/143 stopped by SIGHUP/SIGINT/SIGTERM.

set -u

CARGO="${CARGO:-cargo}"
if [ "$#" -ge 1 ]; then
  ROOT=$(cd "$1" && pwd) || exit 2
else
  ROOT=$(cd "$(dirname "$0")/.." && pwd) || exit 2
fi

die() {
  printf '%s\n' "ERROR: $*" >&2
  exit 2
}

# Where cargo-audit will look for audit.toml, and a refusal to run cargo at all when that cannot be
# known. This comes BEFORE the first cargo call on purpose: with a relative HOME a rustup-managed cargo
# starts installing the pinned toolchain into the current directory (observed: 259 MB under ./relative),
# which is not something a "refusing to audit" error should cost anyone.
env_bad=0
cargo_home=""
case ${CARGO_HOME:-} in
  "")
    case ${HOME:-} in
      /*) cargo_home="$HOME/.cargo" ;;
      *)
        printf '%s\n' "ERROR: CARGO_HOME is not set and HOME is '${HOME:-unset}', not an absolute path, so this script cannot tell where cargo-audit will look for audit.toml (it would use the password-database home, not HOME). Set CARGO_HOME or HOME to an absolute path." >&2
        env_bad=1
        ;;
    esac
    ;;
  /*) cargo_home=$CARGO_HOME ;;
  *)
    printf '%s\n' "ERROR: CARGO_HOME='$CARGO_HOME' is not an absolute path. cargo-audit resolves a relative CARGO_HOME against each lock directory, so an audit.toml there would be obeyed and this script would not see it. Set CARGO_HOME to an absolute path or unset it." >&2
    env_bad=1
    ;;
esac
if [ "$env_bad" -ne 0 ]; then
  echo "Refusing to run: fix the environment above first (exit 2 means 'could not check', never 'clean')." >&2
  exit 2
fi

version_out=$(cd "$ROOT" && "$CARGO" audit --version 2>&1 </dev/null)
version_status=$?
if [ "$version_status" -ne 0 ]; then
  {
    echo "ERROR: 'cargo audit' is not available (CARGO=$CARGO)."
    case $version_out in
      *lias*)
        echo "  cargo mentioned an alias, so this may be an alias for 'audit' (an [alias] audit = ... in a"
        echo "  .cargo/config.toml, or CARGO_ALIAS_AUDIT in the environment) that replaces the cargo-audit"
        echo "  subcommand. cargo said: $(printf '%s\n' "$version_out" | head -n 1)"
        ;;
    esac
    echo "  Install it once with:  cargo install cargo-audit --locked"
    echo "  CI installs the same tool with taiki-e/install-action (tool: cargo-audit)."
    echo "  CARGO must be a single executable path; arguments such as '+toolchain' are not accepted."
    echo "  Put a wrapper script on the path to choose a toolchain."
  } >&2
  exit 2
fi

if [ -e "$ROOT/.gitmodules" ]; then
  die "$ROOT/.gitmodules exists, and git cannot list the files inside a submodule, so a submodule's Cargo.lock would go unaudited without a word. Refusing to report a result."
fi

listing=$(mktemp "${TMPDIR:-/tmp}/cargo-audit-all.XXXXXX") || die "cannot create a temporary file"
# EXIT removes the file. A signal must END the script, not just run a handler and carry on (a trap
# whose handler returns resumes the script where it was interrupted), so each signal exits with the
# conventional 128+n status, which in turn runs the EXIT trap.
trap 'rm -f "$listing"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# NUL-separated, so git quotes and splits nothing. The pathspec only narrows what git has to list;
# the exact-basename filter below is what decides what is a root.
git -C "$ROOT" ls-files -z --cached --others --exclude-standard -- '*Cargo.lock' >"$listing" || die "could not list Cargo.lock files with git in $ROOT"

if [ "$(tr -cd '\n' <"$listing" | wc -c | tr -d ' ')" != "0" ]; then
  die "a Cargo.lock path under $ROOT contains a newline; refusing to guess which directories to audit."
fi

roots=""
while IFS= read -r lock; do
  case $lock in
    Cargo.lock | */Cargo.lock) ;;
    *) continue ;; # NotCargo.lock, untracked.Cargo.lock, ...: matched by the pathspec, not a root
  esac
  roots="$roots$lock
"
done <<EOF
$(tr '\0' '\n' <"$listing")
EOF

if [ -z "$roots" ]; then
  die "no Cargo.lock found under $ROOT -- refusing to report 'clean' for zero roots."
fi

# A lock's directory relative to ROOT. Parameter expansion, not dirname: `dirname -- x` is needed
# for a top-level directory whose name starts with '-', and avoiding the process avoids the question.
root_dir() {
  case $1 in
    */*) printf '%s\n' "${1%/*}" ;;
    *) printf '%s\n' "." ;;
  esac
}

# --- precondition pass: nothing is audited until every root can be audited honestly ------------

bad=0
if [ -n "$cargo_home" ] && [ -e "$cargo_home/audit.toml" ]; then
  printf '%s\n' "ERROR: $cargo_home/audit.toml exists. cargo-audit reads it and it can silently ignore advisories, so a PASS here could disagree with CI. Move it aside, or run cargo audit by hand." >&2
  bad=1
fi
if [ -e "$ROOT/.cargo/audit.toml" ]; then
  printf '%s\n' "ERROR: $ROOT/.cargo/audit.toml exists. cargo-audit reads it and it can silently ignore advisories, so a PASS here could disagree with CI." >&2
  bad=1
fi

while IFS= read -r lock; do
  [ -n "$lock" ] || continue
  dir=$(root_dir "$lock")
  if [ ! -f "$ROOT/$lock" ]; then
    printf '%s\n' "ERROR: $lock is listed by git but missing from the working tree; cargo audit would generate a fresh lockfile in $dir and audit that instead." >&2
    bad=1
    continue
  fi
  if [ "$dir" != "." ] && [ -e "$ROOT/$dir/.cargo/audit.toml" ]; then
    printf '%s\n' "ERROR: $dir/.cargo/audit.toml exists. cargo-audit reads it and it can silently ignore advisories, so a PASS here could disagree with CI." >&2
    bad=1
  fi
  shadow=$( (cd "$ROOT/$dir" && "$CARGO" audit --version 2>&1 >/dev/null </dev/null) | grep -c 'is shadowing an external subcommand')
  if [ "$shadow" != "0" ]; then
    printf '%s\n' "ERROR: in $dir, cargo warns that a user-defined alias 'audit' is shadowing the external cargo-audit subcommand. 'cargo audit' there runs the alias, not the audit, and could exit 0 without auditing anything. Remove the [alias] audit entry from the .cargo/config.toml that defines it (or unset CARGO_ALIAS_AUDIT)." >&2
    bad=1
  fi
  first=$( (cd "$ROOT/$dir" && "$CARGO" audit --version 2>/dev/null </dev/null) | head -n 1)
  case $first in
    *cargo-audit*) ;;
    *)
      printf '%s\n' "ERROR: in $dir, 'cargo audit --version' printed '${first:-nothing}', not a cargo-audit version. Something shadows the subcommand, most likely an [alias] audit = ... in a .cargo/config.toml, and cargo audit would run that instead and could exit 0 without auditing anything." >&2
      bad=1
      ;;
  esac
done <<EOF
$roots
EOF

if [ "$bad" -ne 0 ]; then
  echo "Refusing to audit: fix the errors above first (exit 2 means 'could not check', never 'clean')." >&2
  exit 2
fi

# --- audit pass ---------------------------------------------------------------------------------

failed=0
summary=""
while IFS= read -r lock; do
  [ -n "$lock" ] || continue
  dir=$(root_dir "$lock")
  printf '%s\n' ">> cargo audit in $dir"
  if (cd "$ROOT/$dir" && "$CARGO" audit </dev/null); then
    summary="$summary
  PASS  $dir"
  else
    status=$?
    summary="$summary
  FAIL  $dir (cargo audit exit $status)"
    failed=$((failed + 1))
  fi
done <<EOF
$roots
EOF

echo
printf '%s\n' "cargo audit summary:$summary"
if [ "$failed" -ne 0 ]; then
  printf '%s\n' "FAILED: $failed Cargo root(s) did not pass (vulnerable, or could not be checked; see above)." >&2
  exit 1
fi
echo "OK: every Cargo root passed cargo audit (warnings, if any, are printed above and do not fail)."
