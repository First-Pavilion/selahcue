#!/bin/sh
# SelahCue NFR measurement (walking-skeleton acceptance):
#   NFR: idle memory <= 300 MB · cold start <= 3 s
#
# Method (honest about what is measured):
#   * cold start — process launch until the control server advertises its endpoint
#     file. This is a PROXY: the server thread starts alongside window creation, so
#     it tracks process init closely, but "first visible frame" is not instrumented
#     yet. Both should sit well inside the budget on a release build.
#   * idle memory — max RSS sampled over 5 s after a 3 s settle, with the app idle
#     (two windows composited, no timer, no clients).
#
# Runs the RELEASE build; briefly opens the two output windows. Usage: make nfr

set -eu

BUDGET_RSS_MB=300
BUDGET_COLD_S=3.0

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DESKTOP="$ROOT/implementation/desktop"
ENDPOINT=$(python3 -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'selahcue-operator-endpoint.json'))")
BIN="$DESKTOP/target/release/selahcue-output"

echo ">> building release binary…"
cargo build --release -q --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-desktop

# Run ONE release-build budget test and PROVE it ran, before the caller may print PASS.
#
#   budget_test <crate> <test-file> <test-name> <label>
#
# Why this is not just `cargo test ... <name>`: the test is selected by a NAME FILTER, and
# `cargo test` exits 0 when a filter matches zero tests ("running 0 tests ... 0 passed; N
# filtered out"). So a test that is renamed, moved to another file, deleted, or marked
# #[ignore] makes the command SUCCEED while measuring nothing -- and with the output thrown
# away and an unconditional PASS echoed after it, the budget goes silently unenforced behind
# a green line. These three gates are the ONLY place the release budgets they name are
# enforced (`make ci` runs debug builds with generous tripwires), so that is a dead budget,
# not a cosmetic slip. ClickUp 86ak66jwh. (The same "referenced by name but no longer
# defined" shape as 86ak643rc Defect 2.)
#
# These three are NOT every release-only budget in the tree. Two more have a release arm that
# no gate here runs, because only debug builds ever execute them, so their real budgets are
# enforced by nothing today:
#   * go_live_latency_holds_for_the_longest_verse_auto_fit  (selahcue-present/tests/test_present.rs, 150 ms)
#   * scripture_stage_to_live_latency_is_measured           (selahcue-app/tests/test_controller.rs, 300 ms median)
# Gating them is a separate change, tracked outside 86ak66jwh; this helper is what they would call.
#
# So this asserts the thing RAN, not merely that it did not fail: the captured output must
# contain the line libtest prints for one executed, passing test -- `test <name> ... ok` (a
# test inside a `mod` prints `test <mod>::<name> ... ok`, which the optional prefix covers).
# `0 passed; N filtered out`, `... ignored` and `... FAILED` all lack that line. The check is
# on the full test name, not the substring the cargo filter matches, so a rename to
# `<name>_v2` (which the filter would still select) is caught too.
#
# CONTRACT -- what this does and does not prove:
#   * It matches the test NAME, not its body. A same-named test whose body was emptied or
#     stubbed still passes this check; what a budget test asserts stays a review concern.
#   * <test-name> must be a plain identifier, optionally `mod::name`. It is used both as cargo's
#     substring filter and as an extended regex. Regex metacharacters are escaped below so a
#     `.` cannot match loosely, but anything beyond identifier characters and `::` is
#     unsupported -- do not pass a path, a glob or a pattern.
#
# Both a failing test and a missing one stop the script non-zero. The missing-test message
# names the test and the file it should be in, so the next reader sees "the budget's test no
# longer exists" instead of having to re-derive it. stdout is captured (and shown only on
# failure); stderr is left alone so build errors reach the terminal as before.
budget_test() {
  bt_crate=$1
  bt_file=$2
  bt_name=$3
  bt_label=$4
  bt_where="implementation/desktop/crates/$bt_crate/tests/$bt_file.rs"
  # The name as a literal in an extended regex: backslash-escape every ERE metacharacter.
  bt_re=$(printf '%s' "$bt_name" | sed 's/[][\.*^$+?(){}|]/\\&/g')

  bt_out=$(mktemp "${TMPDIR:-/tmp}/selahcue-nfr-test.XXXXXX")
  # Remove the capture file if interrupted mid-run. Cleared again on the success path below;
  # every other path exits the script, and the app-launch half installs its own trap later.
  trap 'rm -f "$bt_out"; exit 1' INT TERM
  # `if` so a failing cargo does not trip `set -e` before the diagnosis below is printed.
  #
  # `-- --format pretty` is what makes the match below reliable. libtest's DEFAULT format
  # already prints `test <name> ... ok`, but cargo forwards a quiet setting to it (`-q`, the
  # CARGO_TERM_QUIET=true environment variable, or `[term] quiet = true` in a cargo config) and
  # libtest then prints one `.` per test and no names, so every gate would go RED with a
  # misleading "renamed" message. Pinning the format makes the capture independent of the
  # caller's cargo configuration. (Observed: CARGO_TERM_QUIET=true gives dots without it and
  # names with it.) We pass no `-q` of our own, for the same reason it was dropped from the old
  # call. Cargo's own "Running"/"Finished" chatter goes to stderr, not into the capture.
  # (Checked: CARGO_TERM_COLOR=always, which CI exports, colours cargo's stderr but does not
  # reach libtest's redirected stdout, so the match below is not affected by it.)
  if cargo test --release --manifest-path "$DESKTOP/Cargo.toml" -p "$bt_crate" \
      --test "$bt_file" "$bt_name" -- --format pretty >"$bt_out"; then
    bt_rc=0
  else
    bt_rc=$?
  fi

  if [ "$bt_rc" -ne 0 ]; then
    echo "FAIL: release-build budget test '$bt_name' failed or did not build (cargo exit $bt_rc)." >&2
    echo "      Budget: $bt_label" >&2
    echo "      Test:   $bt_where" >&2
    echo "      cargo test output:" >&2
    sed 's/^/    /' "$bt_out" >&2
    rm -f "$bt_out"
    exit 1
  fi

  if ! grep -Eq "^test (.+::)?${bt_re} \.\.\. ok\$" "$bt_out"; then
    echo "FAIL: no test named exactly '$bt_name' reported ok, so this budget gate cannot vouch for it." >&2
    echo "      Budget:   $bt_label" >&2
    echo "      Expected: a test named '$bt_name' in $bt_where" >&2
    echo "      cargo exited 0, but that test did not run and pass. It may have been renamed" >&2
    echo "      (even to a name that still matches cargo's filter), moved, deleted or marked" >&2
    echo "      #[ignore]. Restore it, or point this script at its new name -- never leave the" >&2
    echo "      gate pointing at nothing." >&2
    echo "      cargo test output:" >&2
    sed 's/^/    /' "$bt_out" >&2
    rm -f "$bt_out"
    exit 1
  fi

  rm -f "$bt_out"
  trap - INT TERM
  echo "   $bt_label PASS"
}

echo ">> enforcing the release-build slide-trigger budget (150 ms)…"
budget_test selahcue-present test_present go_live_slide_trigger_latency_is_within_budget \
  "slide-trigger latency: within 150 ms (release)"

# The 300 ms release arms below exist ONLY here: `make ci` runs debug builds, whose
# generous tripwires do not enforce the real budgets. Skipping these would leave the
# release budgets dead (that exact gap shipped the follow-burst budget unenforced).
echo ">> enforcing the release-build scripture follow-burst budget (300 ms)…"
budget_test selahcue-present test_present scripture_follow_burst_with_an_image_theme_is_within_budget \
  "scripture follow burst (image theme): within 300 ms (release)"

echo ">> enforcing the release-build multi-surface burst budget (300 ms)…"
budget_test selahcue-engine test_raster a_multi_surface_verse_burst_keeps_every_surface_prefix_cached \
  "multi-surface (3-prefix) burst: within 300 ms (release)"

if pgrep -f selahcue-output >/dev/null 2>&1; then
  echo "WARNING: a selahcue-output instance is already running; results would be"
  echo "         polluted and its endpoint file will be replaced. Close it first."
  exit 1
fi
rm -f "$ENDPOINT"
# Portable temp file: `mktemp -t <prefix>` is a BSD/macOS-ism that GNU mktemp
# rejects ("too few X's"). An explicit XXXXXX template works on both.
APP_LOG=$(mktemp "${TMPDIR:-/tmp}/selahcue-nfr-log.XXXXXX")
echo ">> launching selahcue-output (release)…"
T0=$(python3 -c "import time;print(time.time())")
"$BIN" >"$APP_LOG" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT INT TERM

# Cold-start proxy: wait for the endpoint file (tight poll).
COLD=""
i=0
while [ "$i" -lt 600 ]; do
  if [ -f "$ENDPOINT" ]; then
    COLD=$(python3 -c "import time;print(round(time.time()-$T0,3))")
    break
  fi
  i=$((i+1))
  sleep 0.01
done
if [ -z "$COLD" ]; then
  echo "FAIL: endpoint never appeared (did the app start?)"
  exit 1
fi

# Idle memory: settle, then sample max RSS for 5 s. The process must be ALIVE for
# the whole window — a crashed app must never yield a fabricated PASS.
sleep 3
MAX_KB=0
j=0
while [ "$j" -lt 10 ]; do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "FAIL: the app died during the idle-memory window. Last output:"
    tail -5 "$APP_LOG" | sed 's/^/    /'
    rm -f "$ENDPOINT"
    exit 1
  fi
  KB=$(ps -o rss= -p "$PID" | tr -d ' ' || echo 0)
  [ -n "$KB" ] && [ "$KB" -gt "$MAX_KB" ] && MAX_KB=$KB
  j=$((j+1))
  sleep 0.5
done
kill "$PID" 2>/dev/null || true
trap - EXIT INT TERM
# The SIGTERM bypasses the app's own clean-exit endpoint removal — clean up here so
# a later operator shell never auto-connects to this dead measurement instance.
rm -f "$ENDPOINT"
if [ "$MAX_KB" -eq 0 ]; then
  echo "FAIL: no RSS samples collected (process not measurable)."
  exit 1
fi

MAX_MB=$(python3 -c "print(round($MAX_KB/1024,1))")
COLD_OK=$(python3 -c "print('PASS' if $COLD <= $BUDGET_COLD_S else 'FAIL')")
RSS_OK=$(python3 -c "print('PASS' if $MAX_MB <= $BUDGET_RSS_MB else 'FAIL')")

echo ""
echo "  NFR results (release build, $(uname -s) $(uname -m))"
echo "  --------------------------------------------------------"
echo "  cold start (to control-server-ready) : ${COLD}s  (budget ${BUDGET_COLD_S}s)  $COLD_OK"
echo "  idle memory (max RSS over 5s)        : ${MAX_MB}MB (budget ${BUDGET_RSS_MB}MB) $RSS_OK"
echo ""
[ "$COLD_OK" = "PASS" ] && [ "$RSS_OK" = "PASS" ]
