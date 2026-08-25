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

echo ">> enforcing the release-build slide-trigger budget (150 ms)…"
cargo test --release -q --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-present \
  --test test_present go_live_slide_trigger_latency_is_within_budget >/dev/null
echo "   slide-trigger latency: within 150 ms (release) PASS"

# The 300 ms release arms below exist ONLY here: `make ci` runs debug builds, whose
# generous tripwires do not enforce the real budgets. Skipping these would leave the
# release budgets dead (that exact gap shipped the follow-burst budget unenforced).
echo ">> enforcing the release-build scripture follow-burst budget (300 ms)…"
cargo test --release -q --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-present \
  --test test_present scripture_follow_burst_with_an_image_theme_is_within_budget >/dev/null
echo "   scripture follow burst (image theme): within 300 ms (release) PASS"

echo ">> enforcing the release-build multi-surface burst budget (300 ms)…"
cargo test --release -q --manifest-path "$DESKTOP/Cargo.toml" -p selahcue-engine \
  --test test_raster a_multi_surface_verse_burst_keeps_every_surface_prefix_cached >/dev/null
echo "   multi-surface (3-prefix) burst: within 300 ms (release) PASS"

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
